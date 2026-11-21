#!/usr/bin/env python3
"""Sync: keep the live psai clone, the user's fork and this machine's tools in step. Used by the sync and retro skills
through `psai sync ...` / `psai retro ...`. Nothing here runs on its own: no startup check, no schedule.

  check    the out-of-sync check, deterministic and cheap: new commits on the fork or upstream (short-timeout fetch),
           an install that doesn't match HEAD, pending migrations, ledger sessions or staged changes not yet in a PR,
           and tool drift since the last scan. Exit 0 = in sync, 1 = out of sync.
  update   fast-forward only, keeping local inbox entries; then re-install (which runs pending migrations).
           Exit 4 = a conflict: nothing changed ("psai update waiting: needs you").
  drift    what changed in the tools since the last scan: skill folders, global instruction files (outside psai's
           own lines) and Claude's memory folders. `baseline` records the current state.
  stage    print (and create) the stage worktree, where customize-harness edits and validates. Never live.
  pr       build ONE branch in a separate worktree with everything staged or captured (stage worktree + the live
           clone's uncommitted user-owned files + pending retro reports as the description), push it to the fork
           and open the PR when there's a remote and gh, else leave it local. Nothing to change: no branch.
  migrate  run pending migrations/NNNN-*.sh once per machine.
  run      check; in sync -> done; else update and list what the skill still has to judge (drift, pending items).

State lives in <state> (ledger.state_dir): sync.json, installed.json, migrations.json, drift.json, proposed.json,
reports/, prs/, stage/ and worktrees/.
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import harness  # noqa: E402
import ledger  # noqa: E402
import skills as skillreg  # noqa: E402

FETCH_TIMEOUT = int(os.environ.get("PSAI_FETCH_TIMEOUT", "10"))
CONFLICT = 4
GIT_ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0")
GIT_ENV.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=5")


def root_of(root=None):
    """The repo with the user's content: the overlay in the stacks layout, the clone in a single-root home."""
    return os.path.realpath(ledger.home(root).overlay_path)


def framework_of(root=None):
    """The framework clone: its install.sh, migrations/ and HEAD (what's installed)."""
    r = os.path.realpath(ledger.root_dir(root))
    if os.path.exists(os.path.join(r, "install.sh")):
        return r
    return os.path.realpath(ledger.home(root).framework)


def st(root, *parts):
    return os.path.join(ledger.state_dir(root), *parts)


def g(root, *args, timeout=None, strip=True):
    """git -C root args -> (rc, stdout)."""
    try:
        p = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, env=GIT_ENV, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, ""
    return p.returncode, (p.stdout.strip() if strip else p.stdout)


def gv(root, *args):
    rc, out = g(root, *args)
    return out if rc == 0 else ""


def rev(root, ref):
    return gv(root, "rev-parse", "-q", "--verify", f"{ref}^{{commit}}")


def ancestor(root, a, b):
    return g(root, "merge-base", "--is-ancestor", a, b)[0] == 0


def has_remote(root, name):
    return name in gv(root, "remote").split()


def default_branch(root, remote):
    ref = gv(root, "symbolic-ref", "-q", f"refs/remotes/{remote}/HEAD")
    if ref:
        return ref.replace(f"refs/remotes/{remote}/", "", 1)
    for b in ("main", "master"):
        if rev(root, f"{remote}/{b}"):
            return b
    return ""


def follow_ref(root):
    """The remote branch the live clone fast-forwards to: the current branch's upstream, else origin/<branch>."""
    up = gv(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if up:
        return up
    br = gv(root, "rev-parse", "--abbrev-ref", "HEAD")
    if br and br != "HEAD" and rev(root, f"origin/{br}"):
        return f"origin/{br}"
    return ""


def base_ref(root):
    """Where PR branches start: the fork's default branch, else the live HEAD."""
    if has_remote(root, "origin"):
        b = default_branch(root, "origin")
        if b and rev(root, f"origin/{b}"):
            return f"origin/{b}"
    return "HEAD"


def fetch(root):
    out = {}
    for r in ("origin", "upstream"):
        if has_remote(root, r):
            rc, _ = g(root, "fetch", "-q", "--no-tags", r, timeout=FETCH_TIMEOUT)
            out[r] = "ok" if rc == 0 else ("timeout" if rc == 124 else "failed")
    return out


def sha256(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return "deleted"


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


# ---------- staged and captured changes ----------
def user_owned(root, paths):
    """In a single-root home, the paths LAYOUT.md gives the user; the overlay repo is all the user's."""
    if not os.path.exists(os.path.join(root, "install.sh")):
        return set(paths)
    return set(harness.user_files(root, os.path.join(root, "LAYOUT.md"), list(paths)))


def stage_dir(root):
    return st(root, "stage")


def ensure_stage(root):
    """The stage worktree (detached, at the live HEAD): customize-harness and retro edit and validate here."""
    root = root_of(root)
    d = stage_dir(root)
    head = rev(root, "HEAD")
    if not os.path.isdir(os.path.join(d, ".git")) and not os.path.isfile(os.path.join(d, ".git")):
        g(root, "worktree", "prune")
        os.makedirs(os.path.dirname(d), exist_ok=True)
        rc, _ = g(root, "worktree", "add", "-q", "--detach", d, "HEAD")
        if rc:
            raise RuntimeError(f"can't create the stage worktree at {d}")
        open(st(root, "stage.base"), "w").write(head + "\n")
    elif not stage_changes(root) and (read(st(root, "stage.base")) or "").strip() != head:
        g(d, "checkout", "-q", "--detach", head)
        open(st(root, "stage.base"), "w").write(head + "\n")
    return d


def _name_status(out):
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            yield parts[0][:1], parts[-1]


def stage_changes(root):
    """{path: source file or None (deleted)} for everything changed in the stage worktree since its base."""
    d = stage_dir(root)
    base = (read(st(root, "stage.base")) or "").strip()
    if not base or not os.path.exists(os.path.join(d, ".git")):
        return {}
    out = {}
    for s, p in _name_status(gv(d, "diff", "--no-renames", "--name-status", base)):
        out[p] = None if s == "D" else os.path.join(d, p)
    for p in gv(d, "ls-files", "--others", "--exclude-standard").splitlines():
        if p:
            out[p] = os.path.join(d, p)
    return out


def live_changes(root):
    """{path: source or None} for the live clone's uncommitted changes (inbox entries, adopted skills, ...)."""
    out = {}
    rc, s = g(root, "status", "--porcelain=v1", "-z", "-uall", "--no-renames", strip=False)
    for line in s.split("\0") if rc == 0 else []:
        if len(line) < 4:
            continue
        xy, p = line[:2], line[3:]
        out[p] = None if "D" in xy else os.path.join(root, p)
    return out


def proposed(root):
    return ledger.read_json(st(root, "proposed.json"), {}) or {}


def pending_changes(root):
    """(changes, skipped): user-owned changes not yet proposed in a PR; skipped = paths psai would never PR
    (upstream-owned files edited locally)."""
    root = root_of(root)
    cand = dict(live_changes(root))
    cand.update(stage_changes(root))  # the stage wins over the live copy
    mine = user_owned(root, cand)
    done = proposed(root)
    changes = {p: src for p, src in cand.items() if p in mine and done.get(p) != (sha256(src) if src else "deleted")}
    skipped = sorted(p for p in cand if p not in mine)
    return changes, skipped


def reports(root):
    return sorted(glob.glob(st(root, "reports", "*.md")))


def consume_reports(root, paths):
    for p in paths:
        os.makedirs(st(root, "reports", "done"), exist_ok=True)
        shutil.move(p, st(root, "reports", "done", os.path.basename(p)))


# ---------- drift ----------
def instruction_files(home):
    cfg = skillreg._cfg(home)
    return [("~/.claude/CLAUDE.md", os.path.join(home, ".claude", "CLAUDE.md")),
            ("~/.config/opencode/AGENTS.md", os.path.join(cfg, "opencode", "AGENTS.md")),
            ("~/.pi/agent/AGENTS.md", os.path.join(home, ".pi", "agent", "AGENTS.md")),
            ("~/.omp/agent/AGENTS.md", os.path.join(home, ".omp", "agent", "AGENTS.md"))]


PSAI_LINE = re.compile(r"^@~/\.(psai|harness)/")  # legacy import lines are psai's own


def _strip_psai(text):
    out, inb = [], False
    for line in text.splitlines():
        if line.strip() == "<!-- harness:start -->":
            inb = True
        elif line.strip() == "<!-- harness:end -->":
            inb = False
        elif not inb and not PSAI_LINE.match(line):
            out.append(line)
    return "\n".join(out).strip()


def _sig(path):
    try:
        s = os.stat(path)
        return f"{s.st_size}:{int(s.st_mtime)}"
    except OSError:
        return "missing"


def fingerprints(root, home=None):
    """{key: {item: signature}} for the tools' skill folders (unmanaged entries only), the global instruction files
    and Claude's memory folders."""
    home = home or os.path.expanduser("~")
    real_root = os.path.realpath(root)
    try:
        ignore = set(skillreg.config(root)["ignore"])
    except Exception:  # noqa: BLE001
        ignore = set()
    fp = {}
    for label, d, _ in skillreg.user_dirs(home):
        items = {}
        for n, p in skillreg._entries(d):
            if n in ignore or (os.path.islink(p) and skillreg._under(os.path.realpath(p), real_root)):
                continue
            items[n] = f"{os.path.realpath(p)}:{_sig(os.path.join(p, 'SKILL.md'))}"
        if items:
            fp[f"skills {label}"] = items
    for label, path in instruction_files(home):
        text = read(path)
        if text is not None and _strip_psai(text):
            fp[f"instructions {label}"] = {"content": hashlib.sha256(_strip_psai(text).encode()).hexdigest()[:16]}
    for d in sorted(glob.glob(os.path.join(home, ".claude", "projects", "*", "memory"))):
        items = {}
        for dp, _, fs in os.walk(d):
            for f in fs:
                items[os.path.relpath(os.path.join(dp, f), d)] = _sig(os.path.join(dp, f))
        if items:
            fp[f"memory ~/.claude/projects/{os.path.basename(os.path.dirname(d))}/memory"] = items
    return fp


def drift(root, home=None):
    """{baseline: bool, changed: [keys], details: {key: [added/changed/removed items]}} against the last scan."""
    root = root_of(root)
    now = fingerprints(root, home)
    last = ledger.read_json(st(root, "drift.json"))
    if last is None:
        return {"baseline": False, "changed": sorted(now), "details": {k: sorted(v) for k, v in now.items()}, "now": now}
    last = last.get("fingerprints", {})
    changed, details = [], {}
    for k in sorted(set(now) | set(last)):
        a, b = last.get(k, {}), now.get(k, {})
        if a == b:
            continue
        changed.append(k)
        details[k] = [f"+{i}" for i in sorted(set(b) - set(a))] + [f"-{i}" for i in sorted(set(a) - set(b))] + \
                     [f"~{i}" for i in sorted(set(a) & set(b)) if a[i] != b[i]]
    return {"baseline": True, "changed": changed, "details": details, "now": now}


def record_baseline(root, home=None):
    root = root_of(root)
    ledger.write_json(st(root, "drift.json"), {"at": ledger.now(), "fingerprints": fingerprints(root, home)})


# ---------- install record and migrations ----------
def installed(root):
    return ledger.read_json(st(root, "installed.json"), {}) or {}


def record_install(root):
    root = root_of(root)
    head = rev(framework_of(root), "HEAD") or "unknown"
    if installed(root).get("commit") != head:  # unchanged -> no write (install.sh stays idempotent)
        ledger.write_json(st(root, "installed.json"), {"commit": head, "at": ledger.now(), "version": ledger.version(root)})


def migrations(root):
    return sorted(glob.glob(os.path.join(framework_of(root), "migrations", "[0-9][0-9][0-9][0-9]-*.sh")))


def pending_migrations(root):
    done = ledger.read_json(st(root, "migrations.json"), {}) or {}
    return [m for m in migrations(root) if os.path.basename(m) not in done]


def migrate(root, dry=False, link=None):
    """Run each pending migration once (state in migrations.json). link = the base link path ($PSAI_HOME)."""
    root = root_of(root)
    done = ledger.read_json(st(root, "migrations.json"), {}) or {}
    for m in pending_migrations(root):
        name = os.path.basename(m)
        print(f"{'would: ' if dry else ''}migration {name}")
        env = dict(os.environ, PSAI_REPO=framework_of(root), PSAI_LINK=link or ledger.root_dir(), DRY_RUN="1" if dry else "0")
        p = subprocess.run(["bash", m], env=env)
        if p.returncode:
            print(f"psai: migration {name} failed (exit {p.returncode}); it will run again next time", file=sys.stderr)
            return 1
        if not dry:
            done[name] = ledger.now()
            ledger.write_json(st(root, "migrations.json"), done)
    return 0


# ---------- the check ----------
def upstream_ahead(root):
    """(n new upstream commits not in HEAD, upstream sha), 0 if none or already proposed in a PR."""
    if not has_remote(root, "upstream"):
        return 0, ""
    b = default_branch(root, "upstream")
    sha = rev(root, f"upstream/{b}") if b else ""
    if not sha or ancestor(root, sha, "HEAD"):
        return 0, sha
    if (ledger.read_json(st(root, "sync.json"), {}) or {}).get("upstream_proposed") == sha:
        return 0, sha
    n = gv(root, "rev-list", "--count", f"HEAD..{sha}")
    return int(n or 0), sha


def check(root, do_fetch=True, home=None):
    """[(kind, detail)]: why this machine is out of sync. Empty = in sync."""
    root = root_of(root)
    why = []
    if do_fetch:
        for r, res in fetch(root).items():
            if res != "ok":
                why_fetch = f"fetch {r}: {res}"
                print(f"psai: {why_fetch} (checking against what's known locally)", file=sys.stderr)
    t = follow_ref(root)
    if t:
        head, tip = rev(root, "HEAD"), rev(root, t)
        if tip and head != tip:
            if ancestor(root, head, tip):
                why.append(("behind", f"{gv(root, 'rev-list', '--count', f'HEAD..{tip}')} new commit(s) on {t}"))
            elif not ancestor(root, tip, head):
                why.append(("diverged", f"the live clone and {t} have both moved on"))
    n, _ = upstream_ahead(root)
    if n:
        why.append(("upstream", f"{n} new upstream commit(s) to merge into your fork"))
    inst, fw_head = installed(root).get("commit"), rev(framework_of(root), "HEAD")
    if inst != fw_head:
        why.append(("install", f"installed {(inst or 'never')[:12]}, HEAD is {fw_head[:12]}"))
    pm = pending_migrations(root)
    if pm:
        why.append(("migrations", ", ".join(os.path.basename(m) for m in pm)))
    uns = [r["id"] for r in ledger.records(root) if ledger.unsynced(r)]
    if uns:
        why.append(("unsynced", f"{len(uns)} session(s) captured items not yet in a PR"))
    ch, _ = pending_changes(root)
    if ch:
        why.append(("staged", f"{len(ch)} staged or captured file(s) not yet in a PR: {', '.join(sorted(ch)[:5])}"))
    rp = reports(root)
    if rp:
        why.append(("reports", f"{len(rp)} retro report(s) waiting for a PR"))
    d = drift(root, home)
    if d["changed"]:
        why.append(("drift", ("first scan: " if not d["baseline"] else "") + "; ".join(d["changed"])))
    return why


# ---------- update (ff-only) ----------
def is_inbox(p):
    return p == "knowledge/inbox.md" or bool(re.fullmatch(r"knowledge/roles/[^/]+/inbox\.md", p))


def merge_inbox(incoming, local):
    """Incoming text, plus every local `## ` entry it doesn't already hold."""
    def entries(t):
        return [b.strip() for b in re.split(r"(?m)^(?=## )", t or "") if b.startswith("## ")]
    have = set(entries(incoming))
    extra = [e for e in entries(local) if e not in have]
    if not incoming:
        return local
    return incoming.rstrip("\n") + ("\n\n" + "\n\n".join(extra) + "\n" if extra else "\n")


def update(root, dry=False):
    """-> (status, detail): updated | nothing | conflict | would."""
    root = root_of(root)
    t = follow_ref(root)
    if not t:
        return "nothing", "no remote branch to follow"
    head, tip = rev(root, "HEAD"), rev(root, t)
    if not tip or head == tip or ancestor(root, tip, head):
        return "nothing", f"up to date with {t}"
    if not ancestor(root, head, tip):
        return "conflict", f"the live clone has commits that aren't on {t}; merge or rebase it yourself"
    touched = set(gv(root, "diff", "--name-only", head, tip).splitlines())
    local = live_changes(root)
    tracked_local = {p for p in local if gv(root, "ls-files", "--", p)}
    saved, inbox = {}, {}
    for p in sorted(touched & set(local)):
        cur = read(os.path.join(root, p))
        rc, inc = g(root, "show", f"{tip}:{p}")
        inc = (inc + "\n") if rc == 0 else None
        saved[p] = cur
        if is_inbox(p):
            inbox[p] = cur
        elif cur is None or inc is None or cur.rstrip("\n") != inc.rstrip("\n"):
            return "conflict", f"{p} changed here and on {t}"
    if dry:
        return "would", f"fast-forward {head[:7]}..{tip[:7]} ({len(touched)} file(s)), keeping {len(inbox)} local inbox file(s)"

    def restore():
        for p, cur in saved.items():
            if cur is not None:
                os.makedirs(os.path.dirname(os.path.join(root, p)) or ".", exist_ok=True)
                open(os.path.join(root, p), "w").write(cur)

    for p in saved:
        if p in tracked_local:
            g(root, "checkout", "-q", "HEAD", "--", p)
        elif os.path.exists(os.path.join(root, p)):
            os.remove(os.path.join(root, p))
    rc, _ = g(root, "merge", "-q", "--ff-only", tip)
    if rc:
        g(root, "reset", "-q", "--keep", head)
        restore()
        return "conflict", f"git refused the fast-forward to {t}"
    for p, cur in inbox.items():
        dst = os.path.join(root, p)
        merged = merge_inbox(read(dst), cur)
        with open(dst, "w") as f:
            f.write(merged)
    return "updated", f"{head[:7]}..{tip[:7]} from {t}"


def reinstall(root):
    if os.environ.get("PSAI_EVAL"):
        print("psai: eval run: install.sh skipped")
        return 0
    return subprocess.run(["bash", os.path.join(framework_of(root), "install.sh")]).returncode


# ---------- the one PR ----------
def host():
    h = os.environ.get("PSAI_HOST") or socket.gethostname().split(".")[0]
    return re.sub(r"[^a-z0-9-]+", "-", h.lower()).strip("-") or "host"


def gh_repo(root):
    url = gv(root, "remote", "get-url", "origin")
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(\.git)?/?$", url)
    return m.group(1) if m else ""


def _ident(root):
    if gv(root, "config", "user.email"):
        return []
    return ["-c", "user.name=psai", "-c", "user.email=psai@localhost"]


def build_pr(root, kind="sync", body="", title=None, local=False):
    """Build one branch with everything pending. -> dict(branch, files, pushed, url) or None (nothing to change)."""
    root = root_of(root)
    changes, skipped = pending_changes(root)
    reps = reports(root)
    n_up, up_sha = upstream_ahead(root) if kind == "sync" else (0, "")
    if not changes and not n_up:
        consume_reports(root, reps)
        return None
    base = base_ref(root)
    stamp = datetime.datetime.now()
    branch = f"psai/{kind}-{host()}-{stamp:%Y%m%d}"
    if rev(root, branch) or rev(root, f"origin/{branch}"):
        branch += f"-{stamp:%H%M%S}"
    wt = st(root, "worktrees", branch.replace("/", "-"))
    shutil.rmtree(wt, ignore_errors=True)
    g(root, "worktree", "prune")
    os.makedirs(os.path.dirname(wt), exist_ok=True)
    rc, _ = g(root, "worktree", "add", "-q", "-b", branch, wt, base)
    if rc:
        raise RuntimeError(f"can't create the PR worktree for {branch}")
    notes = []
    try:
        if n_up:
            b = default_branch(root, "upstream")
            if g(wt, *_ident(root), "merge", "-q", "--no-edit", f"upstream/{b}")[0]:
                g(wt, "merge", "--abort")
                notes.append(f"upstream has {n_up} new commit(s), but merging upstream/{b} conflicts: merge it yourself.")
                n_up = 0
            else:
                notes.append(f"merges {n_up} new upstream commit(s) from upstream/{b}.")
        for p, src in sorted(changes.items()):
            dst = os.path.join(wt, p)
            if src is None:
                if os.path.lexists(dst):
                    os.remove(dst)
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
        g(wt, "add", "-A")
        staged = gv(wt, "diff", "--cached", "--name-only").splitlines()
        if not staged and not n_up:
            g(root, "worktree", "remove", "--force", wt)
            g(root, "branch", "-D", branch)
            consume_reports(root, reps)
            return None
        title = title or (f"psai {kind}: {host()} {stamp:%Y-%m-%d}")
        if staged:
            g(wt, *_ident(root), "commit", "-q", "-m", title)
    finally:
        if os.path.exists(wt):
            g(root, "worktree", "remove", "--force", wt)
    files = sorted(changes)
    text = [f"# {title}", ""]
    if body.strip():
        text += [body.strip(), ""]
    for r in reps:
        text += [read(r).strip(), ""]
    text += ["## What this PR carries"] + [f"- `{p}`" + (" (deleted)" if changes[p] is None else "") for p in files]
    text += [f"- {n}" for n in notes]
    if skipped:
        text += ["", "Not included (upstream-owned files edited locally; change them upstream instead): "
                 + ", ".join(f"`{p}`" for p in skipped)]
    text += ["", f"Built by `psai {kind}` on {host()} from {base} ({rev(root, base)[:12]})."]
    body_path = st(root, "prs", branch.replace("/", "-") + ".md")
    os.makedirs(os.path.dirname(body_path), exist_ok=True)
    open(body_path, "w").write("\n".join(text) + "\n")
    pushed, url = False, ""
    if not local and has_remote(root, "origin"):
        pushed = g(root, "push", "-q", "-u", "origin", branch, timeout=60)[0] == 0
        repo = gh_repo(root)
        if pushed and repo and shutil.which("gh"):
            b = default_branch(root, "origin") or "main"
            p = subprocess.run(["gh", "pr", "create", "--repo", repo, "--head", branch, "--base", b, "--title", title,
                                "--body-file", body_path], capture_output=True, text=True, cwd=root)
            url = p.stdout.strip() if p.returncode == 0 else ""
    # record: these contents are proposed; the stage is emptied; the sessions are synced; the reports are used
    done = proposed(root)
    for p, src in changes.items():
        done[p] = sha256(src) if src else "deleted"
    ledger.write_json(st(root, "proposed.json"), done)
    if stage_changes(root):
        d = stage_dir(root)
        g(d, "checkout", "-q", "--detach", "--force", rev(root, "HEAD"))
        g(d, "clean", "-fdq")
        open(st(root, "stage.base"), "w").write(rev(root, "HEAD") + "\n")
    for r in ledger.records(root):
        if ledger.unsynced(r) or (r.get("end") is None and not r.get("synced")):
            r["synced"] = branch
            ledger.save(r, root)
    consume_reports(root, reps)
    s = ledger.read_json(st(root, "sync.json"), {}) or {}
    s.update(last_pr=branch, last_pr_at=ledger.now())
    if up_sha and n_up:
        s["upstream_proposed"] = up_sha
    ledger.write_json(st(root, "sync.json"), s)
    return {"branch": branch, "files": files, "pushed": pushed, "url": url, "body": body_path,
            "next": "" if url or local else (
                f"push it and open the PR: git -C {root} push -u origin {branch} && gh pr create --head {branch} "
                f"--body-file {body_path}" if not pushed else f"open the PR: gh pr create --head {branch} --body-file {body_path}")}


def mark_synced(root):
    s = ledger.read_json(st(root, "sync.json"), {}) or {}
    s["last_sync"] = ledger.now()
    ledger.write_json(st(root, "sync.json"), s)


# ---------- CLI ----------
def _print_pr(res, kind):
    if not res:
        print(f"psai {kind}: nothing worth changing: no PR")
        return
    print(f"psai {kind}: branch {res['branch']} ({len(res['files'])} file(s)); description: {res['body']}")
    print("  pushed to origin" if res["pushed"] else "  local only (no origin, or push failed)")
    if res["url"]:
        print(f"  PR: {res['url']}")
    elif res["next"]:
        print(f"  next: {res['next']}")


def main(argv):
    ap = argparse.ArgumentParser(prog="psai sync", description="Sync this machine with the fork; see the module doc.")
    ap.add_argument("cmd", nargs="?", default="run",
                    choices=["run", "check", "update", "drift", "baseline", "stage", "pr", "migrate", "installed"])
    ap.add_argument("--root", default=None)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--local", action="store_true", help="pr: don't push or open the PR")
    ap.add_argument("--kind", default="sync", choices=["sync", "retro"])
    ap.add_argument("--title", default=None)
    ap.add_argument("--body-file", default=None)
    ap.add_argument("--record", action="store_true", help="installed: record HEAD as installed (install.sh)")
    ap.add_argument("--link", default=None, help="migrate: the base link path")
    a = ap.parse_args(argv)
    root = root_of(a.root)

    if a.cmd == "installed":
        if a.record:
            record_install(root)
        print(json.dumps(installed(root)))
        return 0
    if a.cmd == "migrate":
        return migrate(root, a.dry_run, a.link)
    if a.cmd == "stage":
        print(ensure_stage(root))
        return 0
    if a.cmd == "baseline":
        record_baseline(root)
        print("psai: drift baseline recorded")
        return 0
    if a.cmd == "drift":
        d = drift(root)
        d.pop("now", None)
        if a.json:
            print(json.dumps(d, indent=1))
        elif not d["changed"]:
            print("psai: no drift since the last scan")
        for k in [] if a.json else d["changed"]:
            print(f"{k}: {' '.join(d['details'].get(k, []))}")
        return 0
    if a.cmd == "update":
        status, detail = update(root, a.dry_run)
        print(f"psai update: {status}: {detail}")
        if status == "conflict":
            print("psai update waiting: needs you")
            return CONFLICT
        if status == "updated":
            return reinstall(root)
        return 0
    if a.cmd == "pr":
        body = read(a.body_file) if a.body_file else ""
        res = build_pr(root, a.kind, body or "", a.title, a.local)
        if a.kind == "sync":
            record_baseline(root)
            mark_synced(root)
        _print_pr(res, a.kind)
        return 0
    why = check(root, do_fetch=not a.no_fetch)
    if a.cmd == "check":
        if a.json:
            print(json.dumps([{"kind": k, "detail": d} for k, d in why], indent=1))
        else:
            print("psai: in sync" if not why else "psai: out of sync")
            for k, d in why:
                print(f"  {k}: {d}")
        return 1 if why else 0
    # run: the deterministic part of the sync skill
    if not why:
        mark_synced(root)
        print("psai: in sync; nothing to do")
        return 0
    print("psai: out of sync")
    for k, d in why:
        print(f"  {k}: {d}")
    kinds = {k for k, _ in why}
    if "diverged" in kinds:
        print("psai update waiting: needs you (the live clone and the fork have diverged); nothing changed")
        return CONFLICT
    if kinds & {"behind", "install", "migrations"}:
        status, detail = update(root)
        print(f"update: {status}: {detail}")
        if status == "conflict":
            print("psai update waiting: needs you; nothing changed")
            return CONFLICT
        if reinstall(root):
            print("psai: install.sh failed; see its output", file=sys.stderr)
            return 1
    d = drift(root)
    if d["changed"]:
        print("drift to judge (adopt what's worth keeping by staging it, then `psai sync pr`):")
        for k in d["changed"]:
            print(f"  {k}: {' '.join(d['details'].get(k, [])[:20])}")
    print("next: stage anything worth keeping from the drift, then run `psai sync pr` (one PR for this machine)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
