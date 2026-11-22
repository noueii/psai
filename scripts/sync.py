#!/usr/bin/env python3
"""Sync: keep this machine's framework, overlay, stacks and tools in step (ADR 0011, sections 7 and 14). Used by
the sync and retro skills through `psai sync ...` / `psai retro ...`. Nothing here runs on its own: no startup check,
no schedule. psai writes only to its targets: the overlay (`nostack`) and the stacks you author (`dev` in stacks.yaml).

  check    the out-of-sync check, deterministic and cheap: new commits on the overlay's remote, a newer framework
           release, a newer release of a pinned stack in range (short-timeout fetches), an install that doesn't match
           the framework, pending migrations, ledger sessions or staged changes not yet in a PR, and tool drift.
           Exit 0 = in sync, 1 = out of sync.
  update   fast-forward the overlay (keeping local inbox entries) and the framework, then re-install (which runs
           pending migrations). A framework release that an installed stack's psai range excludes is refused unless
           --force (those stacks are then disabled in your overlay until they update). Exit 4 = a conflict: nothing
           changed ("psai update waiting: needs you"). Pinned stacks move with `psai stack update`.
  drift    what changed in the tools since the last scan: skill folders, global instruction files (outside psai's
           own lines) and Claude's memory folders. `baseline` records the current state.
  stage    print (and create) a target's stage worktree (state/stage/<stack>/, --stack, default the overlay),
           where customize-harness and the retro edit and validate. Never live.
  pr       build one branch per target with changes (its stage worktree + its live uncommitted files), each with the
           pending retro reports as the description; push it and open the PR when the target has a remote and gh,
           else leave it local. Nothing to change: no branch.
  migrate  run pending migrations/NNNN-*.sh once per machine.
  run      check; in sync -> done; else update and list what the skill still has to judge (drift, pending items).

State lives in <state> (ledger.state_dir): sync.json, installed.json, migrations.json, drift.json, proposed.json,
reports/, prs/, stage/<stack>/ and worktrees/. A single-root home (a fork clone, before migration 0002) is one target,
the clone, filtered by LAYOUT.md's owner column as before.
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
    """Where PR branches start: the target's default branch on origin, else its HEAD."""
    if has_remote(root, "origin"):
        b = default_branch(root, "origin")
        if b and rev(root, f"origin/{b}"):
            return f"origin/{b}"
    return "HEAD"


def fetch(root):
    out = {}
    for r in ("origin",):
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


# ---------- targets, stages, staged and captured changes ----------
def targets(root):
    """[(stack, repo path)] psai may write: the overlay, then each dev stack (one you author). Pinned stacks never."""
    h = ledger.home(root)
    out = [("nostack", os.path.realpath(h.overlay_path))]
    out += [(st_.name, os.path.realpath(st_.path)) for st_ in h.stacks if st_.mode == "dev"]
    return out


def target_path(root, stack="nostack"):
    for n, p in targets(root):
        if n == stack:
            return p
    raise RuntimeError(f"{stack} is not a target: only your overlay (nostack) and the stacks you author (dev) are")


def user_owned(root, paths):
    """In a single-root home, the paths LAYOUT.md gives the user; a target repo (the overlay, a dev stack) is all
    yours."""
    if not os.path.exists(os.path.join(root, "install.sh")):
        return set(paths)
    return set(harness.user_files(root, os.path.join(root, "LAYOUT.md"), list(paths)))


def stage_dir(root, stack="nostack"):
    return st(root, "stage", stack)


def _stage_base(root, stack):
    return st(root, "stage", f"{stack}.base")


def ensure_stage(root, stack="nostack"):
    """A target's stage worktree (detached, at the target's HEAD): customize-harness and the retro edit and validate
    here, never in the live repo."""
    repo = target_path(root, stack)
    d = stage_dir(root, stack)
    head = rev(repo, "HEAD")
    if not os.path.isdir(os.path.join(d, ".git")) and not os.path.isfile(os.path.join(d, ".git")):
        g(repo, "worktree", "prune")
        os.makedirs(os.path.dirname(d), exist_ok=True)
        rc, _ = g(repo, "worktree", "add", "-q", "--detach", d, "HEAD")
        if rc:
            raise RuntimeError(f"can't create the stage worktree at {d}")
        open(_stage_base(root, stack), "w").write(head + "\n")
    elif not stage_changes(root, stack) and (read(_stage_base(root, stack)) or "").strip() != head:
        g(d, "checkout", "-q", "--detach", head)
        open(_stage_base(root, stack), "w").write(head + "\n")
    return d


def _name_status(out):
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            yield parts[0][:1], parts[-1]


def stage_changes(root, stack="nostack"):
    """{path: source file or None (deleted)} for everything changed in a target's stage worktree since its base."""
    d = stage_dir(root, stack)
    base = (read(_stage_base(root, stack)) or "").strip()
    if not base or not os.path.exists(os.path.join(d, ".git")):
        return {}
    out = {}
    for s_, p in _name_status(gv(d, "diff", "--no-renames", "--name-status", base)):
        out[p] = None if s_ == "D" else os.path.join(d, p)
    for p in gv(d, "ls-files", "--others", "--exclude-standard").splitlines():
        if p:
            out[p] = os.path.join(d, p)
    return out


def live_changes(repo):
    """{path: source or None} for a repo's uncommitted changes (inbox entries, adopted skills, ...)."""
    out = {}
    rc, s_ = g(repo, "status", "--porcelain=v1", "-z", "-uall", "--no-renames", strip=False)
    for line in s_.split("\0") if rc == 0 else []:
        if len(line) < 4:
            continue
        xy, p = line[:2], line[3:]
        out[p] = None if "D" in xy else os.path.join(repo, p)
    return out


def _proposed_all(root):
    d = ledger.read_json(st(root, "proposed.json"), {}) or {}
    if d and not all(isinstance(v, dict) for v in d.values()):
        d = {"nostack": d}  # the one-target format before ADR 0011
    return d


def proposed(root, stack="nostack"):
    return _proposed_all(root).get(stack, {})


def _save_proposed(root, stack, done):
    d = _proposed_all(root)
    d[stack] = done
    ledger.write_json(st(root, "proposed.json"), d)


def pending_changes(root, stack="nostack"):
    """(changes, skipped) for one target: its staged and live changes not yet proposed in a PR; skipped = paths psai
    would never PR (only in a single-root home: upstream-owned files edited locally)."""
    repo = target_path(root, stack)
    cand = dict(live_changes(repo))
    cand.update(stage_changes(root, stack))  # the stage wins over the live copy
    mine = user_owned(repo, cand)
    done = proposed(root, stack)
    changes = {p: src for p, src in cand.items() if p in mine and done.get(p) != (sha256(src) if src else "deleted")}
    skipped = sorted(p for p in cand if p not in mine)
    return changes, skipped


def all_pending(root):
    """{stack: changes} for every target with something to propose."""
    out = {}
    for n, _p in targets(root):
        ch, _ = pending_changes(root, n)
        if ch:
            out[n] = ch
    return out


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
def newer_releases(root, do_fetch=True):
    """[(kind, detail)]: a newer framework release, and a newer release in range for each pinned stack."""
    import resolve  # noqa: PLC0415
    import stacks  # noqa: PLC0415
    h = ledger.home(root)
    out = []
    if h.compat:
        return out
    fw = os.path.realpath(h.framework)
    if do_fetch and has_remote(fw, "origin"):
        g(fw, "fetch", "-q", "--tags", "origin", timeout=FETCH_TIMEOUT)
    cur = resolve._vt(resolve.framework_version(fw))
    newer = [t for v, t in stacks.tags(fw) if v > cur]
    if newer:
        out.append(("framework", f"psai {newer[0]} is out (this is {resolve.framework_version(fw)}): `psai update`"))
    for e in stacks.entries(h):
        if e.get("mode") == "dev":
            continue
        d = os.path.join(h.root, "stacks", e["name"])
        if not os.path.isdir(d):
            continue
        if do_fetch:
            g(d, "fetch", "-q", "--tags", "origin", timeout=FETCH_TIMEOUT)
        rng = " ".join(r["version"] for s_ in h.stacks for r in s_.meta.get("requires") or [] if r.get("name") == e["name"])
        t = stacks.newest_fitting(d, rng or None)
        if t and stacks.pin_of(d, t) != e.get("commit"):
            out.append(("stack", f"{e['name']} {t} is out in range (pinned at {e.get('ref')}): `psai stack update {e['name']}`"))
    return out


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
    why += newer_releases(root, do_fetch)
    inst, fw_head = installed(root).get("commit"), rev(framework_of(root), "HEAD")
    if inst != fw_head:
        why.append(("install", f"installed {(inst or 'never')[:12]}, HEAD is {fw_head[:12]}"))
    pm = pending_migrations(root)
    if pm:
        why.append(("migrations", ", ".join(os.path.basename(m) for m in pm)))
    uns = [r["id"] for r in ledger.records(root) if ledger.unsynced(r)]
    if uns:
        why.append(("unsynced", f"{len(uns)} session(s) captured items not yet in a PR"))
    for n, ch in all_pending(root).items():
        why.append(("staged", f"{n}: {len(ch)} staged or captured file(s) not yet in a PR: {', '.join(sorted(ch)[:5])}"))
    rp = reports(root)
    if rp:
        why.append(("reports", f"{len(rp)} retro report(s) waiting for a PR"))
    d = drift(root, home)
    if d["changed"]:
        why.append(("drift", ("first scan: " if not d["baseline"] else "") + "; ".join(d["changed"])))
    return why


# ---------- update (ff-only) ----------
def is_inbox(p):
    return p == "knowledge/inbox.md" or bool(re.fullmatch(r"knowledge/([^/]+/)?roles/[^/]+/inbox\.md", p))


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


def update_framework(root, dry=False, force=False):
    """-> (status, detail): fast-forward the framework clone (stacks layout only). A release that an installed stack's
    psai range excludes is refused unless force; forcing disables those stacks in your overlay until they update."""
    import resolve  # noqa: PLC0415
    import stacks  # noqa: PLC0415
    h = ledger.home(root)
    if h.compat:
        return "nothing", "a single-root home: the clone is the framework"
    fw = os.path.realpath(h.framework)
    t = follow_ref(fw)
    if not t:
        return "nothing", "the framework has no remote branch to follow"
    head, tip = rev(fw, "HEAD"), rev(fw, t)
    if not tip or head == tip or ancestor(fw, tip, head):
        return "nothing", f"framework up to date with {t}"
    if not ancestor(fw, head, tip):
        return "conflict", f"the framework clone has commits that aren't on {t}; update it yourself"
    try:
        new = (yaml_load(gv(fw, "show", f"{tip}:VERSION")) or "0.0.0").strip()
    except Exception:  # noqa: BLE001
        new = "0.0.0"
    out = [s_.name for s_ in h.stacks if s_.meta.get("psai") and not resolve.in_range(new, s_.meta["psai"])]
    if out and not force:
        return "conflict", (f"psai {new} is outside the psai range of: {', '.join(out)}; update those stacks first, or "
                            "`psai update --force` (they are disabled until they update)")
    if dry:
        return "would", f"fast-forward the framework {head[:7]}..{tip[:7]} (psai {new})"
    if g(fw, "merge", "-q", "--ff-only", tip)[0]:
        return "conflict", f"git refused the framework's fast-forward to {t}"
    if out:
        meta = resolve.load_stack(h.overlay_path)
        meta["disable"] = sorted(set(meta.get("disable") or []) | set(out))
        import yaml  # noqa: PLC0415
        with open(os.path.join(h.overlay_path, "stack.yaml"), "w") as f:
            yaml.safe_dump(meta, f, sort_keys=False)
        print(f"psai: disabled {', '.join(out)} in your overlay until they take psai {new} (`psai stack update`)")
    return "updated", f"framework {head[:7]}..{tip[:7]} (psai {new})"


def yaml_load(text):
    import yaml  # noqa: PLC0415
    return yaml.safe_load(text)


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


def build_pr(root, kind="sync", body="", title=None, local=False, stack="nostack", reps=None):
    """Build one branch in one target repo with everything pending there. -> dict(stack, branch, files, pushed, url)
    or None (nothing to change). Reports are the description; build_prs consumes them."""
    root = root_of(root)
    repo = target_path(root, stack)
    changes, skipped = pending_changes(root, stack)
    reps = reports(root) if reps is None else reps
    if not changes:
        return None
    base = base_ref(repo)
    stamp = datetime.datetime.now()
    branch = f"psai/{kind}-{host()}-{stamp:%Y%m%d}"
    if rev(repo, branch) or rev(repo, f"origin/{branch}"):
        branch += f"-{stamp:%H%M%S}"
    wt = st(root, "worktrees", f"{stack}-" + branch.replace("/", "-"))
    shutil.rmtree(wt, ignore_errors=True)
    g(repo, "worktree", "prune")
    os.makedirs(os.path.dirname(wt), exist_ok=True)
    rc, _ = g(repo, "worktree", "add", "-q", "-b", branch, wt, base)
    if rc:
        raise RuntimeError(f"can't create the PR worktree for {branch} in {repo}")
    try:
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
        if not staged:
            g(repo, "worktree", "remove", "--force", wt)
            g(repo, "branch", "-D", branch)
            return None
        title = title or (f"psai {kind}: {host()} {stamp:%Y-%m-%d}" + ("" if stack == "nostack" else f" ({stack})"))
        g(wt, *_ident(repo), "commit", "-q", "-m", title)
    finally:
        if os.path.exists(wt):
            g(repo, "worktree", "remove", "--force", wt)
    files = sorted(changes)
    text = [f"# {title}", ""]
    if body.strip():
        text += [body.strip(), ""]
    for r in reps:
        text += [read(r).strip(), ""]
    text += ["## What this PR carries"] + [f"- `{p}`" + (" (deleted)" if changes[p] is None else "") for p in files]
    if skipped:
        text += ["", "Not included (upstream-owned files edited locally; change them upstream instead): "
                 + ", ".join(f"`{p}`" for p in skipped)]
    text += ["", f"Built by `psai {kind}` on {host()} in {'your overlay' if stack == 'nostack' else 'the stack ' + stack} "
                 f"from {base} ({rev(repo, base)[:12]})."]
    body_path = st(root, "prs", f"{stack}-" + branch.replace("/", "-") + ".md")
    os.makedirs(os.path.dirname(body_path), exist_ok=True)
    open(body_path, "w").write("\n".join(text) + "\n")
    pushed, url = False, ""
    if not local and has_remote(repo, "origin"):
        pushed = g(repo, "push", "-q", "-u", "origin", branch, timeout=60)[0] == 0
        gh = gh_repo(repo)
        if pushed and gh and shutil.which("gh"):
            b = default_branch(repo, "origin") or "main"
            p = subprocess.run(["gh", "pr", "create", "--repo", gh, "--head", branch, "--base", b, "--title", title,
                                "--body-file", body_path], capture_output=True, text=True, cwd=repo)
            url = p.stdout.strip() if p.returncode == 0 else ""
    # record: these contents are proposed; the stage is emptied
    done = proposed(root, stack)
    for p, src in changes.items():
        done[p] = sha256(src) if src else "deleted"
    _save_proposed(root, stack, done)
    if stage_changes(root, stack):
        d = stage_dir(root, stack)
        g(d, "checkout", "-q", "--detach", "--force", rev(repo, "HEAD"))
        g(d, "clean", "-fdq")
        open(_stage_base(root, stack), "w").write(rev(repo, "HEAD") + "\n")
    return {"stack": stack, "branch": branch, "files": files, "pushed": pushed, "url": url, "body": body_path,
            "next": "" if url or local else (
                f"push it and open the PR: git -C {repo} push -u origin {branch} && gh pr create --head {branch} "
                f"--body-file {body_path}" if not pushed else f"open the PR: gh pr create --head {branch} --body-file {body_path}")}


def build_prs(root, kind="sync", body="", title=None, local=False):
    """One branch per target with changes (ADR 0011, section 7: one PR per target repo per task). Then the reports are
    used and the sessions marked synced. -> [results]."""
    root = root_of(root)
    reps = reports(root)
    out = [r for r in (build_pr(root, kind, body, title, local, n, reps) for n, _p in targets(root)) if r]
    if out:
        for r in ledger.records(root):
            if ledger.unsynced(r) or (r.get("end") is None and not r.get("synced")):
                r["synced"] = ", ".join(x["branch"] + ("" if x["stack"] == "nostack" else f" ({x['stack']})") for x in out)
                ledger.save(r, root)
        s = ledger.read_json(st(root, "sync.json"), {}) or {}
        s.update(last_pr=out[0]["branch"], last_pr_at=ledger.now())
        ledger.write_json(st(root, "sync.json"), s)
    consume_reports(root, reps)
    return out


def mark_synced(root):
    s = ledger.read_json(st(root, "sync.json"), {}) or {}
    s["last_sync"] = ledger.now()
    ledger.write_json(st(root, "sync.json"), s)


# ---------- CLI ----------
def _print_pr(res, kind):
    if not res:
        print(f"psai {kind}: nothing worth changing: no PR")
        return
    for r in res if isinstance(res, list) else [res]:
        _print_one(r, kind)


def _print_one(res, kind):
    where = "your overlay" if res.get("stack", "nostack") == "nostack" else f"the stack {res['stack']}"
    print(f"psai {kind}: branch {res['branch']} in {where} ({len(res['files'])} file(s)); description: {res['body']}")
    print("  pushed to origin" if res["pushed"] else "  local only (no origin, or push failed)")
    if res["url"]:
        print(f"  PR: {res['url']}")
    elif res["next"]:
        print(f"  next: {res['next']}")


def main(argv):
    ap = argparse.ArgumentParser(prog="psai sync", description="Sync this machine: framework, overlay, stacks, tools; see the module doc.")
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
    ap.add_argument("--stack", default="nostack", help="stage: the target (your overlay, or a dev stack)")
    ap.add_argument("--force", action="store_true", help="update: take a framework release some stacks don't support")
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
        print(ensure_stage(root, a.stack))
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
        if not a.no_fetch:
            fetch(root)
            fw = framework_of(root)
            if fw != root and has_remote(fw, "origin"):
                g(fw, "fetch", "-q", "--tags", "origin", timeout=FETCH_TIMEOUT)
        status, detail = update(root, a.dry_run)
        print(f"psai update: {status}: {detail}")
        fst, fdet = update_framework(root, a.dry_run, a.force)
        if fst != "nothing" or not ledger.home(root).compat:
            print(f"psai update: {fst}: {fdet}")
        if "conflict" in (status, fst):
            print("psai update waiting: needs you")
            return CONFLICT
        if "updated" in (status, fst):
            return reinstall(root)
        return 0
    if a.cmd == "pr":
        body = read(a.body_file) if a.body_file else ""
        res = build_prs(root, a.kind, body or "", a.title, a.local)
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
        print("psai update waiting: needs you (your overlay and its remote have diverged); nothing changed")
        return CONFLICT
    if kinds & {"behind", "install", "migrations", "framework"}:
        status, detail = update(root)
        print(f"update: {status}: {detail}")
        fst, fdet = update_framework(root)
        if fst != "nothing":
            print(f"update: {fst}: {fdet}")
        if "conflict" in (status, fst):
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
    if "stack" in kinds:
        print("stacks with a newer release in range: `psai stack update <name>` (it reports overrides whose original changed)")
    print("next: stage anything worth keeping from the drift, then run `psai sync pr` (one PR per target repo)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
