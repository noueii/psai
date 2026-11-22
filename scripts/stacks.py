#!/usr/bin/env python3
"""The home and its stacks (ADR 0011, sections 1.3 and 12). Used by install.sh and `psai stack ...`.

The home ($PSAI_HOME, else ~/.psai):
  framework/      a link to the psai clone install.sh ran from (or a clone at a release tag)
  overlay/        the stack `nostack`, a git repo created on install: stack.yaml, stacks.yaml (the installed
                  stacks), instructions/owner.md, your own content, knowledge and every inbox
  stacks/<name>/  each installed stack: a clone at its pinned ref, or a link to your working clone (dev)
  state/          this machine's local state ($PSAI_STATE moves it)

  stacks.py overlay --home H [--dry-run]                   create the overlay if it's missing
  stacks.py migrate-fork --home H --clone C [--dry-run]    0002: turn a fork clone's ~/.psai link into a home
  stacks.py skill-sources --home H                         name<TAB>link target, for install.sh (first name wins)
  stacks.py packs --home H                                 stack<TAB>name<TAB>url<TAB>path<TAB>ref, for install.sh

  psai stack add <src> [--ref <tag|commit>] [--as <name>] [--dev] [--yes]   src: github:o/r, a git URL or a path
  psai stack remove <name> [--force]       unlink its skills, remove the clone (a dev link only), keep its overrides
  psai stack update [<name>] [--to <ref>]  move pins to the newest release in range; dev stacks: fast-forward only
  psai stack list [--skills] [--json]      name, version, ref, mode, priority, workflows, overrides, warnings;
                                           --skills: which copy of each skill the tools see
  psai stack sync                          install everything stacks.yaml lists (a new machine)
  psai stack diff <name> [<path>]          the change since the pin, or an override against its original
  psai stack override <stack>:<path> [--in <dir>]   copy a file into overrides/ (records .base.yaml) to change it
  psai stack check <name>                  L0 + L2 for one stack with your overrides in place
Adding a stack never runs its code: no install hooks, no migrations.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import resolve as res  # noqa: E402
import skills as skillreg  # noqa: E402

FW = os.path.dirname(HERE)
OVERLAY_README = """# nostack: your overlay

Your own psai stack, created by install.sh. It always wins over the stacks you install (ADR 0011):
- `stacks.yaml`: the stacks installed on this machine (`psai stack add|remove|update|list`);
- `instructions/owner.md`: your rules for every task;
- your own workflows, roles, steps, guides, templates, `my-skills/` and `skills.yaml`, as in any stack
  (referenced as `nostack:<name>`);
- `knowledge/`: your knowledge and every inbox;
- `overrides/<stack>/<path>`: your replacement for one stack's file.

Push it to a remote of your own to move your setup to another machine:
`git clone <your-overlay> ~/.psai/overlay && psai stack sync`.
"""


def say(dry, msg):
    print(("would: " if dry else "") + msg)


def git(d, *args, check=True):
    env = dict(os.environ)
    # an identity for psai's own commits when the user has none configured
    for k, v in (("GIT_AUTHOR_NAME", "psai"), ("GIT_AUTHOR_EMAIL", "psai@localhost"),
                 ("GIT_COMMITTER_NAME", "psai"), ("GIT_COMMITTER_EMAIL", "psai@localhost")):
        if not env.get(k) and not subprocess.run(["git", "-C", d, "config", "user." + k.split("_")[-1].lower()],
                                                 capture_output=True).stdout.strip():
            env[k] = v
    p = subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, env=env)
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(args)} in {d}: {p.stderr.strip()}")
    return p.stdout.strip()


def overlay_meta():
    major = res._vt(res.framework_version(FW))[0]
    return {"schema": 1, "name": res.OVERLAY, "version": "0.0.0",
            "description": "My overlay: my own content and my adjustments to the stacks I install.",
            "psai": f">={major}.0 <{major + 1}"}


def init_overlay(home, dry=False):
    """Create overlay/ (a git repo, the stack nostack) when it's missing. Never touches an existing one."""
    o = os.path.join(home, "overlay")
    if os.path.exists(o):
        return o
    say(dry, f"create the overlay {o} (stack nostack, a git repo)")
    if dry:
        return o
    os.makedirs(os.path.join(o, "instructions"))
    with open(os.path.join(o, "stack.yaml"), "w") as f:
        yaml.safe_dump(overlay_meta(), f, sort_keys=False)
    with open(os.path.join(o, "stacks.yaml"), "w") as f:
        f.write("# The stacks installed on this machine; psai stack add|remove|update writes it.\nstacks: []\n")
    with open(os.path.join(o, "README.md"), "w") as f:
        f.write(OVERLAY_README)
    git(o, "init", "-q", "-b", "main")
    git(o, "add", "-A")
    git(o, "commit", "-q", "-m", "psai: create the overlay")
    return o


def migrate_fork(home, clone, dry=False):
    """Migration 0002 (ADR 0011, section 12): `home` is a link to a fork clone. Make it a home: framework/ links the
    clone, the fork's user-owned files (by its LAYOUT.md owner column) go into the overlay with no prefix (they stay
    stack-local, now nostack:), .state/ moves to state/ and .skills-cache/ to state/skills-cache/nostack/. The clone's
    files are never changed."""
    import harness  # noqa: PLC0415
    clone = os.path.realpath(clone)
    files = subprocess.run(["git", "-C", clone, "ls-files", "-co", "--exclude-standard"],
                           capture_output=True, text=True).stdout.split("\n")
    layout = os.path.join(clone, "LAYOUT.md")
    mine = harness.user_files(clone, layout, [f for f in files if f])
    say(dry, f"turn {home} (a link to the fork {clone}) into a psai home; framework/ links the clone")
    if not dry:
        os.remove(home)
        os.makedirs(os.path.join(home, "stacks"))
        os.symlink(clone, os.path.join(home, "framework"))
    o = init_overlay(home, dry)
    for f in mine:
        say(dry, f"copy {f} into the overlay")
        if not dry:
            os.makedirs(os.path.dirname(os.path.join(o, f)) or o, exist_ok=True)
            shutil.copy2(os.path.join(clone, f), os.path.join(o, f))
    if not os.environ.get("PSAI_STATE"):
        for src, dst in ((".state", "state"), (".skills-cache", os.path.join("state", "skills-cache", res.OVERLAY))):
            s, d = os.path.join(clone, src), os.path.join(home, dst)
            if os.path.isdir(s) and not os.path.exists(d):
                say(dry, f"move {s} -> {d}")
                if not dry:
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.move(s, d)
    if not dry and mine:
        git(o, "add", "-A")
        git(o, "commit", "-q", "-m", f"psai: content migrated from the fork {clone}")
    print(f"psai: {len(mine)} file(s) of yours moved into {o}. The clone {clone} is untouched; framework/ links it.")
    return 0


def ranked_stacks(h):
    """The installed stacks by routing priority (the overlay's `priority:` wins over a stack's own), then their
    stacks.yaml order: who gets a skill's bare name in the tools' folders after the overlay."""
    import index  # noqa: PLC0415
    over = index.settings(h)["priority"]
    return sorted(h.stacks, key=lambda st: (-int(over.get(st.name, st.priority)), st.order))


def skill_candidates(home):
    """{name: [(stack, link target, what)]}, the copy the tools see first (ADR 0011, section 9.2): the framework's
    (its names are reserved), then the overlay's (my-skills/, then its skills.yaml packs), then each stack's by
    priority. Every target goes through the home path (framework/, overlay/, stacks/, state/)."""
    h = res.Home(home)
    _, dirs, packs_ = skillreg.sources(home)
    pk = {stack: (sroot, cache) for stack, sroot, cache in packs_}
    my = {stack: d for stack, _k, _l, d in dirs}
    order = ["psai", res.OVERLAY] + [st.name for st in ranked_stacks(h)]
    out = {}
    for stack in order:
        if stack in my:
            for n, _p in skillreg._entries(my[stack]):
                out.setdefault(n, []).append((stack, os.path.join(my[stack], n),
                                              "psai's skills/" if stack == "psai" else f"{stack}:my-skills/"))
        if stack in pk:
            sroot, cache = pk[stack]
            for e in skillreg.config(sroot)["skills"]:
                if not isinstance(e, dict) or not e.get("name"):
                    continue
                p = os.path.normpath(os.path.join(cache, e["name"], str(e.get("path") or ".").strip("/")))
                if os.path.isfile(os.path.join(p, "SKILL.md")):
                    out.setdefault(e["name"], []).append((stack, p, f"{stack}:skills.yaml"))
    return out


def skill_sources(home):
    """(name, link target) for every skill psai links into the tools' flat folders: one copy per name, the first in
    skill_candidates' order. The others aren't linked bare (roles still get their own stack's copy through the skills
    brief, which gives the SKILL.md path); each clash is reported on stderr."""
    out = []
    for n, cands in sorted(skill_candidates(home).items()):
        out.append((n, cands[0][1]))
        for stack, _t, what in cands[1:]:
            if cands[0][0] == "psai":
                print(f"skip: {what}{n} uses a name psai reserves; rename it (e.g. {stack}-{n})", file=sys.stderr)
            else:
                print(f"skip: {what}{n}: the tools see {cands[0][2]}{n} under this name; roles of {stack} still "
                      "get theirs", file=sys.stderr)
    return out


def packs(home):
    """(stack, name, url, path, ref) for each pinned skills.yaml entry of the overlay and the installed stacks."""
    out = []
    _, _, ps = skillreg.sources(home)
    for stack, sroot, _cache in ps:
        for e in skillreg.config(sroot)["skills"]:
            if isinstance(e, dict) and all(e.get(k) for k in ("name", "source", "path", "ref")):
                if skillreg.pinned(e["ref"]):
                    out.append((stack, e["name"], skillreg.source_url(e["source"]), str(e["path"]), str(e["ref"])))
                else:
                    print(f"skip: {stack}: skills.yaml entry {e['name']} is not pinned (ref {e['ref']})", file=sys.stderr)
    return out


# ---------- psai stack add|remove|update|list|sync|diff (ADR 0011, section 11) ----------
TAG_RX = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class StackError(Exception):
    pass


def entries(h):
    p = os.path.join(h.overlay_path, "stacks.yaml")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return (yaml.safe_load(f) or {}).get("stacks") or []


def save_entries(h, ents):
    p = os.path.join(h.overlay_path, "stacks.yaml")
    with open(p, "w") as f:
        f.write("# The stacks installed on this machine; psai stack add|remove|update writes it.\n")
        yaml.safe_dump({"stacks": ents}, f, sort_keys=False, default_flow_style=None)


def source_url(src):
    """github:o/r -> its https URL; a local folder -> its absolute path; anything else as is."""
    src = str(src)
    if src.startswith("github:"):
        return f"https://github.com/{src[len('github:'):].strip('/')}.git"
    if os.path.isdir(os.path.expanduser(src)):
        return os.path.abspath(os.path.expanduser(src))
    return src


def tags(clone):
    """[(version tuple, tag)] of the clone's release tags (vX.Y.Z), newest first."""
    out = []
    for t in git(clone, "tag", "-l", check=False).split():
        m = TAG_RX.match(t)
        if m:
            out.append((tuple(int(x) for x in m.groups()), t))
    return sorted(out, reverse=True)


def pin_of(clone, ref):
    """The commit for a tag or a commit id; a branch (or anything else) is refused: a stack is always pinned."""
    c = git(clone, "rev-parse", "-q", "--verify", f"refs/tags/{ref}^{{commit}}", check=False)
    if c:
        return c
    if re.match(r"^[0-9a-f]{7,40}$", str(ref)):
        c = git(clone, "rev-parse", "-q", "--verify", f"{ref}^{{commit}}", check=False)
        if c:
            return c
    raise StackError(f"ref {ref!r} is not a tag or a commit of this stack (a branch is never pinned)")


def meta_at(clone, commit):
    try:
        return yaml.safe_load(git(clone, "show", f"{commit}:stack.yaml")) or {}
    except (RuntimeError, yaml.YAMLError):
        return {}


def fw_version():
    return res.framework_version(FW)


def fits(meta, rng=None):
    """True when a stack.yaml's psai range takes this framework (and its version is in `rng`, if given)."""
    try:
        return res.in_range(fw_version(), meta.get("psai", "")) and (not rng or res.in_range(meta.get("version", "0"), rng))
    except ValueError:
        return False


def newest_fitting(clone, rng=None):
    for _v, t in tags(clone):
        if fits(meta_at(clone, pin_of(clone, t)), rng):
            return t
    return None


def scripts_in(path):
    """Files in a stack's skills that an agent could run (everything under my-skills/ but SKILL.md and .md)."""
    out = []
    d = os.path.join(path, "my-skills")
    for dp, _, fs in os.walk(d):
        for f in fs:
            if not f.endswith(".md"):
                out.append(os.path.relpath(os.path.join(dp, f), path))
    return sorted(out)


def summary(path, meta, name):
    """What a stack would inject and ship: shown before `stack add` asks to confirm (ADR 0011, section 18)."""
    lines = [f"stack {name} {meta.get('version', '?')}: {meta.get('description', '')}"]
    if meta.get("author"):
        lines.append(f"  author: {meta['author'].get('name', '')} {('(github ' + meta['author']['github'] + ')') if meta['author'].get('github') else ''}".rstrip())
    exp = meta.get("exports") or {}
    lines.append("  exports: " + ("; ".join(f"{k}: {v if v == '*' else ', '.join(v)}" for k, v in exp.items()) or "nothing"))
    d = os.path.join(path, "workflows")
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith(".yaml") and not f.endswith(".cases.yaml") and not f.startswith("ROUTING"):
            with open(os.path.join(d, f)) as fh:
                wf = yaml.safe_load(fh) or {}
            lines.append(f"  injected: - {name}:{wf.get('name', f[:-5])}: {' '.join(str(wf.get('when', '')).split())}")
    ins = os.path.join(path, "instructions", "stack.md")
    if os.path.exists(ins):
        lines.append(f"  injected: instructions/stack.md ({len(open(ins).read().split())} words)")
    sc = scripts_in(path)
    lines.append("  skill scripts (run only when an agent uses that skill): " + (", ".join(sc) or "none"))
    if meta.get("requires"):
        lines.append("  requires: " + ", ".join(f"{r.get('name')} {r.get('version')}" for r in meta["requires"]))
    return "\n".join(lines)


def confirm(text, yes):
    print(text)
    if yes:
        return True
    if not sys.stdin.isatty():
        raise StackError("not confirmed: pass --yes to install without asking")
    return input("Install it? [y/N] ").strip().lower() in ("y", "yes")


def relink(h):
    """Link the stacks' skills into the tools' folders (install.sh --relink)."""
    if os.environ.get("PSAI_EVAL"):
        return 0
    return subprocess.run(["bash", os.path.join(FW, "install.sh"), "--relink"],
                          env=dict(os.environ, PSAI_HOME=h.root), stdout=subprocess.DEVNULL).returncode


def add(src, ref=None, as_=None, dev=False, yes=False, h=None, rng=None, why=""):
    """Install a stack (ADR 0011, section 11). Never runs anything from the stack."""
    h = h or res.Home()
    if h.compat:
        raise StackError(f"{h.root} isn't a stacks-layout home yet; run install.sh first")
    url = source_url(src)
    os.makedirs(os.path.join(h.root, "stacks"), exist_ok=True)
    tmp = None
    if dev:
        if not os.path.isdir(url):
            raise StackError(f"--dev takes your working clone (a local folder), not {src}")
        path, commit = url, git(url, "rev-parse", "HEAD", check=False)
        meta = res.load_stack(path)
    else:
        import tempfile  # noqa: PLC0415
        tmp = tempfile.mkdtemp(prefix=".adding-", dir=os.path.join(h.root, "stacks"))
        os.rmdir(tmp)
        p = subprocess.run(["git", "clone", "-q", "--no-checkout", url, tmp], capture_output=True, text=True)
        if p.returncode:
            raise StackError(f"can't fetch {src}: {p.stderr.strip()}")
        try:
            if not ref:
                ref = newest_fitting(tmp, rng)
                if not ref:
                    raise StackError(f"{src} has no release tag (vX.Y.Z) that takes psai {fw_version()}"
                                     + (f" and is in {rng}" if rng else "") + "; pass --ref <tag or commit>")
            commit = pin_of(tmp, ref)
            git(tmp, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", commit)
            path, meta = tmp, res.load_stack(tmp)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
    try:
        errs = res.validate_stack(meta) if meta else ["no stack.yaml"]
        if errs:
            raise StackError(f"{src} is not a valid stack: " + "; ".join(errs))
        name = as_ or meta["name"]
        if name in res.RESERVED or not res.NAME_RX.match(name):
            raise StackError(f"can't install a stack as {name!r} (reserved or not a valid name); use --as <name>")
        if h.get(name) is not None or os.path.lexists(os.path.join(h.root, "stacks", name)):
            raise StackError(f"a stack named {name} is already installed; use --as <other name>")
        if not fits(meta):
            raise StackError(f"{name} {meta.get('version')} needs psai {meta.get('psai')}; this is psai {fw_version()}")
        if rng and not res.in_range(meta.get("version", "0"), rng):
            raise StackError(f"{name} {meta.get('version')} is not in {rng}{why}")
        for r in meta.get("requires") or []:
            dep = h.get(r["name"])
            if dep is not None:
                v = dep.meta.get("version", "0")
                if not res.in_range(v, r["version"]):
                    raise StackError(f"conflict: {name} requires {r['name']} {r['version']}, but {r['name']} {v} is "
                                     "installed (one version per stack); update or remove it first")
        if not confirm(summary(path, meta, name), yes):
            raise StackError("not installed")
        for r in meta.get("requires") or []:
            if h.get(r["name"]) is None:
                print(f"psai: {name} requires {r['name']} {r['version']}: installing it")
                add(r["source"], h=h, yes=True, rng=r["version"], as_=r["name"], why=f" (required by {name})")
                h = res.Home(h.root)
        dest = os.path.join(h.root, "stacks", name)
        if dev:
            os.symlink(path, dest)
        else:
            os.rename(tmp, dest)
            tmp = None
        ents = entries(h)
        e = {"name": name, "source": str(src) if not os.path.isdir(os.path.expanduser(str(src))) else url,
             "ref": str(ref) if ref else None, "commit": commit, "version": str(meta.get("version")),
             "mode": "dev" if dev else "pinned"}
        ents.append({k: v for k, v in e.items() if v is not None})
        save_entries(h, ents)
        relink(res.Home(h.root))
        print(f"psai: installed {name} {meta.get('version')} ({'dev: ' + path if dev else 'pinned at ' + str(ref)})")
        return 0
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def remove(name, force=False, h=None):
    h = h or res.Home()
    ents = entries(h)
    if not any(e.get("name") == name for e in ents):
        raise StackError(f"no stack {name} installed")
    users = [s.name for s in h.stacks if s.name != name and any(r.get("name") == name for r in s.meta.get("requires") or [])]
    if users and not force:
        raise StackError(f"{', '.join(users)} require(s) {name}; remove them first (or --force)")
    dest = os.path.join(h.root, "stacks", name)
    if os.path.islink(dest):
        os.remove(dest)
        print(f"unlink {dest} (your clone stays)")
    elif os.path.isdir(dest):
        shutil.rmtree(dest)
        print(f"remove {dest}")
    save_entries(h, [e for e in ents if e.get("name") != name])
    relink(res.Home(h.root))
    ov = os.path.join(h.overlay_path, "overrides", name)
    n = sum(len(fs) for _, _, fs in os.walk(ov)) if os.path.isdir(ov) else 0
    print(f"psai: removed {name}" + (f"; kept your {n} override file(s) in {ov}" if n else ""))
    return 0


def update(name=None, to=None, h=None):
    h = h or res.Home()
    ents = entries(h)
    todo = [e for e in ents if not name or e.get("name") == name]
    if name and not todo:
        raise StackError(f"no stack {name} installed")
    for e in todo:
        dest = os.path.join(h.root, "stacks", e["name"])
        if e.get("mode") == "dev":
            up = git(dest, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
            if not up:
                print(f"{e['name']}: dev, no upstream branch to fast-forward to")
                continue
            p = subprocess.run(["git", "-C", dest, "pull", "-q", "--ff-only"], capture_output=True, text=True)
            print(f"{e['name']}: dev, " + ("fast-forwarded" if p.returncode == 0 else f"not fast-forwarded: {p.stderr.strip()}"))
            e["commit"] = git(dest, "rev-parse", "HEAD", check=False)
            report_drift(h, e["name"])
            continue
        git(dest, "fetch", "-q", "--tags", "origin", check=False)
        rng = " ".join(r["version"] for s in h.stacks for r in s.meta.get("requires") or [] if r.get("name") == e["name"])
        target = to or newest_fitting(dest, rng or None)
        if not target:
            print(f"{e['name']}: no release tag takes psai {fw_version()}" + (f" within {rng}" if rng else ""))
            continue
        commit = pin_of(dest, target)
        meta = meta_at(dest, commit)
        if to and (not fits(meta) or (rng and not res.in_range(meta.get("version", "0"), rng))):
            raise StackError(f"{e['name']} {target} doesn't take psai {fw_version()} or breaks {rng}")
        if commit == e.get("commit"):
            print(f"{e['name']}: up to date at {e.get('ref')}")
            continue
        git(dest, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", commit)
        print(f"{e['name']}: {e.get('ref')} -> {target}")
        e.update(ref=target, commit=commit, version=str(meta.get("version")))
        report_drift(h, e["name"])
    save_entries(h, ents)
    relink(res.Home(h.root))
    return 0


def skills_listing(h=None, as_json=False):
    """Which copy of each skill the tools see under its bare name, and the copies they don't (ADR 0011, 9.2)."""
    h = h or res.Home()
    rows = [{"name": n, "tools_see": c[0][0], "path": c[0][1], "hidden": [x[0] for x in c[1:]]}
            for n, c in sorted(skill_candidates(h.root).items())]
    if as_json:
        print(json.dumps(rows, indent=1))
        return 0
    for r in rows:
        print(f"{r['name']:32} tools see {r['tools_see']}" + (f"; not linked bare: {', '.join(r['hidden'])} "
                                                              "(their roles still get their own copy)" if r["hidden"] else ""))
    return 0


def listing(h=None, as_json=False):
    h = h or res.Home()
    rows = []
    for e in entries(h):
        st = h.get(e.get("name"))
        path = os.path.join(h.root, "stacks", e.get("name", ""))
        meta = st.meta if st and os.path.exists(path) else {}
        wfs = [f for f in os.listdir(os.path.join(path, "workflows"))
               if f.endswith(".yaml") and not f.endswith(".cases.yaml") and not f.startswith("ROUTING")] \
            if os.path.isdir(os.path.join(path, "workflows")) else []
        ov = os.path.join(h.overlay_path, "overrides", e.get("name", ""))
        warn = []
        if not os.path.exists(path):
            warn.append("missing here (psai stack sync)")
        elif meta and not fits(meta):
            warn.append(f"needs psai {meta.get('psai')}")
        dr = drifted(h, e.get("name")) if os.path.exists(path) else []
        if dr:
            warn.append(f"{len(dr)} override(s) changed upstream (psai stack diff {e.get('name')} <path>)")
        rows.append({"name": e.get("name"), "version": meta.get("version", e.get("version")), "ref": e.get("ref"),
                     "mode": e.get("mode", "pinned"), "priority": st.priority if st else None, "workflows": len(wfs),
                     "exports": meta.get("exports") or {},
                     "overrides": len(overrides_of(h, e.get("name", ""))),
                     "warnings": warn})
    if as_json:
        print(json.dumps(rows, indent=1))
        return 0
    if not rows:
        print("no stacks installed (psai stack add <github:owner/repo | git URL | path>)")
    for r in rows:
        print(f"{r['name']:16} {str(r['version']):10} {str(r['ref'] or '-'):12} {r['mode']:7} prio {r['priority']}  "
              f"{r['workflows']} workflow(s), {r['overrides']} override(s)" + (f"  [{'; '.join(r['warnings'])}]" if r["warnings"] else ""))
    return 0


def sync_all(h=None):
    """Install everything stacks.yaml lists that isn't here yet (a new machine), at the recorded commit."""
    h = h or res.Home()
    missing = 0
    for e in entries(h):
        dest = os.path.join(h.root, "stacks", e["name"])
        if os.path.lexists(dest):
            continue
        if e.get("mode") == "dev":
            print(f"{e['name']}: a dev stack; link your clone: psai stack remove {e['name']} && psai stack add --dev <clone>")
            missing += 1
            continue
        p = subprocess.run(["git", "clone", "-q", "--no-checkout", source_url(e["source"]), dest], capture_output=True, text=True)
        if p.returncode:
            print(f"{e['name']}: can't fetch {e['source']}: {p.stderr.strip()}")
            missing += 1
            continue
        git(dest, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", e.get("commit") or pin_of(dest, e["ref"]))
        print(f"{e['name']}: installed at {e.get('ref')}")
    relink(res.Home(h.root))
    return 1 if missing else 0


def diff(name, path=None, h=None):
    h = h or res.Home()
    e = next((x for x in entries(h) if x.get("name") == name), None)
    if not e:
        raise StackError(f"no stack {name} installed")
    dest = os.path.join(h.root, "stacks", name)
    ov = os.path.join(h.overlay_path, "overrides", name, path) if path else None
    if ov and os.path.exists(ov):
        return subprocess.run(["diff", "-u", os.path.join(dest, path), ov]).returncode and 0
    if e.get("mode") == "dev":
        return subprocess.run(["git", "-C", dest, "diff", e.get("commit", "HEAD"), "--", *([path] if path else [])]).returncode
    git(dest, "fetch", "-q", "--tags", "origin", check=False)
    newest = (tags(dest) or [(None, None)])[0][1]
    if not newest or pin_of(dest, newest) == e.get("commit"):
        print(f"{name}: nothing newer than {e.get('ref')}")
        return 0
    print(f"{name}: {e.get('ref')} -> {newest}")
    subprocess.run(["git", "-C", dest, "log", "--oneline", f"{e['commit']}..{pin_of(dest, newest)}"])
    return subprocess.run(["git", "-C", dest, "diff", "--stat" if not path else "-p", e["commit"], pin_of(dest, newest),
                           "--", *([path] if path else [])]).returncode


# ---------- overrides (ADR 0011, section 6) ----------
def _sha(path):
    import hashlib  # noqa: PLC0415
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def _base_path(h, stack, root=None):
    return os.path.join(root or h.overlay_path, "overrides", stack, ".base.yaml")


def bases(h, stack, root=None):
    try:
        with open(_base_path(h, stack, root)) as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


def override(ref, h=None, root=None):
    """Copy a stack's file into overrides/<stack>/<path> of the overlay (or of `root`, the overlay's stage worktree)
    and record the stack's commit and the original's hash in .base.yaml, so a later update can say it changed.
    Returns the override's path; an existing override is left as is."""
    h = h or res.Home()
    sname, rest = res.split_ref(ref)
    if not sname or sname == res.OVERLAY:
        raise StackError(f"name the stack: <stack>:<path> (your own files in {res.OVERLAY} are edited in place)")
    if sname == "psai":
        raise StackError("the framework's files can't be overridden; change psai by PR")
    st = h.get(sname)
    if st is None:
        raise StackError(f"no stack {sname} installed")
    path = rest.lstrip("/")
    kind = res.kind_of(path)
    if kind == "knowledge":
        raise StackError("knowledge is never overridden: it is additive; capture-knowledge writes to your overlay")
    if path in ("stack.yaml",):
        raise StackError("a stack's identity (stack.yaml) can't be overridden; use your overlay's stack.yaml "
                         "(models, disable, prefer, priority)")
    src = os.path.join(st.path, path)
    if not os.path.exists(src):
        raise StackError(f"{sname}:{path} doesn't exist")
    dst = os.path.join(root or h.overlay_path, "overrides", sname, path)
    if os.path.exists(dst):
        return dst
    if os.path.isdir(src):  # a my-skill: the whole folder
        shutil.copytree(src, dst, symlinks=True)
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    b = bases(h, sname, root)
    b["stack"] = sname
    b.setdefault("files", {})[path] = {"commit": git(st.path, "rev-parse", "HEAD", check=False) or None,
                                       "sha256": _sha(src) if os.path.isfile(src) else _tree_sha(src)}
    with open(_base_path(h, sname, root), "w") as f:
        f.write("# What each override replaced: the stack's commit and the original's hash (psai stack update compares).\n")
        yaml.safe_dump(b, f, sort_keys=True)
    return dst


def _tree_sha(d):
    import hashlib  # noqa: PLC0415
    hs = hashlib.sha256()
    for dp, _, fs in sorted(os.walk(d)):
        for f in sorted(fs):
            p = os.path.join(dp, f)
            hs.update(os.path.relpath(p, d).encode() + b"\0" + (_sha(p) or "").encode())
    return hs.hexdigest()


def overrides_of(h, stack):
    """The override paths of one stack (relative to it), my-skill folders as one entry each."""
    d = os.path.join(h.overlay_path, "overrides", stack)
    out = []
    for dp, dirs, fs in os.walk(d):
        rel = os.path.relpath(dp, d)
        parts = rel.split(os.sep)
        if parts[0] == "my-skills" and len(parts) == 2:
            out.append(rel)
            dirs[:] = []
            continue
        out += [os.path.normpath(os.path.join(rel, f)) for f in fs if f != ".base.yaml"]
    st = h.get(stack)
    # cases next to an overridden workflow are the overlay's own, not an override of anything
    return sorted(p for p in out if not (p.endswith(".cases.yaml") and st and not os.path.exists(os.path.join(st.path, p))))


def drifted(h, stack):
    """[(path, why)] for overrides whose original changed upstream since the override was made."""
    st = h.get(stack)
    if st is None:
        return []
    b = (bases(h, stack).get("files") or {})
    out = []
    for p in overrides_of(h, stack):
        orig = os.path.join(st.path, p)
        if not os.path.exists(orig):
            out.append((p, "removed upstream"))
            continue
        now = _sha(orig) if os.path.isfile(orig) else _tree_sha(orig)
        rec = (b.get(p) or {}).get("sha256")
        if rec and rec != now:
            out.append((p, "changed upstream"))
    return out


def report_drift(h, stack):
    for p, why in drifted(h, stack):
        print(f"{stack}:{p} {why} since you overrode it; diff with `psai stack diff {stack} {p}`")


def effective(h, stack, dest):
    """A copy of a stack with the overlay's overrides in place (and the cases next to them), for validation."""
    st = h.get(stack)
    shutil.copytree(st.path, dest, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    ov = os.path.join(h.overlay_path, "overrides", stack)
    if os.path.isdir(ov):
        shutil.copytree(ov, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".base.yaml"))
    return dest


def check_dir(d, name, h, label=None, overrides=0):
    """L0 (content, refs through resolve, LAYOUT placement, stack.yaml, skills config, fresh diagrams) and L2
    (simulate) for one stack folder. 0 = pass."""
    import graph  # noqa: PLC0415
    import harness  # noqa: PLC0415
    import simulate  # noqa: PLC0415
    label = label or name
    meta_path = os.path.join(d, "stack.yaml")
    errs = harness.validate(d, h) + harness.check_layout(d, os.path.join(FW, "LAYOUT.md"))
    if os.path.exists(meta_path):
        errs += res.validate_stack(res.load_stack(d), overlay=name == res.OVERLAY)
    elif name != res.OVERLAY:
        errs.append("stack.yaml missing (psai new-stack makes one)")
    errs += [f"{s_}: workflow diagram missing or stale (psai graph {label} --update-readme)" for s_ in graph.refresh(d, False)]
    for e in errs:
        print(f"  FAIL {label}: {e}")
    print(f"  {'ok  ' if not errs else 'FAIL'} {label}: content and refs" + (f" ({overrides} override(s) in place)" if overrides else ""))
    if name != res.OVERLAY:  # the tools' skill folders are flat: unprefixed names collide across stacks
        for sk, _p in skillreg._entries(os.path.join(d, "my-skills")):
            if not sk.startswith(f"{name}-"):
                print(f"  warn {label}: my-skills/{sk}: prefix your skill names ({name}-{sk}) so they don't "
                      "collide with other stacks' in the tools' flat folders")
    rc = simulate.main(d)
    return 1 if errs or rc else 0


def check_stack(name, h=None):
    """check_dir for one installed stack, with the overlay's overrides in place of the originals (ADR 0011, 6)."""
    import tempfile  # noqa: PLC0415
    h = h or res.Home()
    if h.get(name) is None:
        raise StackError(f"no stack {name} installed")
    if name == res.OVERLAY:
        return check_dir(h.overlay_path, name, h)
    with tempfile.TemporaryDirectory() as t:
        d = effective(h, name, os.path.join(t, name))
        return check_dir(d, name, h, overrides=len(overrides_of(h, name)))


def check_main(argv):
    """psai check [<stack>|<path>] [--quick]: one stack (installed name or folder), or every installed stack and the
    overlay. The framework's own tests are scripts/check.sh (`psai check --framework`)."""
    args = [a for a in argv if a != "--quick"]
    if "--framework" in args:
        return subprocess.run(["bash", os.path.join(FW, "scripts", "check.sh"), *[a for a in args if a != "--framework"]]).returncode
    h = res.Home()
    if not args:
        names = [res.OVERLAY] + [st.name for st in h.stacks]
        return max([check_stack(n, h) for n in names] or [0])
    rc = 0
    for a in args:
        if os.path.isdir(a):
            d = os.path.abspath(a)
            name = res.load_stack(d).get("name") or res.OVERLAY
            rc = max(rc, check_dir(d, name, h, label=a))
        elif h.get(a) is not None:
            rc = max(rc, check_stack(a, h))
        else:
            print(f"psai check: no installed stack or folder {a!r}", file=sys.stderr)
            rc = 3
    return rc


def new_stack(name, dest=None, description=None, add_it=True, h=None):
    """psai new-stack: copy template/stack, fill stack.yaml, git init, and add it as a dev stack."""
    h = h or res.Home()
    if name in res.RESERVED or not res.NAME_RX.match(name):
        raise StackError(f"{name!r} can't be a stack name: [a-z][a-z0-9-]{{1,31}}, and not psai or nostack")
    dest = os.path.abspath(dest or name)
    if os.path.exists(dest):
        raise StackError(f"{dest} already exists")
    shutil.copytree(os.path.join(FW, "template", "stack"), dest)
    author = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip() or "you"
    major = res._vt(res.framework_version(FW))[0]
    fill = {"__NAME__": name, "__DESCRIPTION__": description or f"The {name} stack: say in one line what it's for.",
            "__AUTHOR__": author, "__PSAI__": f">={major}.0 <{major + 1}"}
    for rel in ("stack.yaml", "README.md"):
        p = os.path.join(dest, rel)
        text = open(p).read()
        for k, v in fill.items():
            text = text.replace(k, v)
        open(p, "w").write(text)
    git(dest, "init", "-q", "-b", "main")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", f"psai new-stack {name}")
    print(f"psai: created the stack {name} in {dest}")
    if add_it and not h.compat:
        add(dest, dev=True, yes=True, h=h)
    return 0


def stack_main(argv):
    ap = argparse.ArgumentParser(prog="psai stack", description="Install and manage stacks (ADR 0011, section 11).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("add", help="install a stack: github:owner/repo, a git URL or a local path")
    a_.add_argument("src")
    a_.add_argument("--ref", help="a tag or a commit (default: the newest release tag that takes this psai)")
    a_.add_argument("--as", dest="as_", help="install it under another name")
    a_.add_argument("--dev", action="store_true", help="link your working clone instead of pinning a copy")
    a_.add_argument("--yes", action="store_true", help="don't ask to confirm")
    r_ = sub.add_parser("remove", help="uninstall a stack (your overrides are kept)")
    r_.add_argument("name")
    r_.add_argument("--force", action="store_true")
    u_ = sub.add_parser("update", help="move pins to the newest release in range (dev stacks: fast-forward only)")
    u_.add_argument("name", nargs="?")
    u_.add_argument("--to", help="a tag or a commit")
    l_ = sub.add_parser("list", help="the installed stacks")
    l_.add_argument("--json", action="store_true")
    l_.add_argument("--skills", action="store_true", help="which copy of each skill the tools see")
    sub.add_parser("sync", help="install everything stacks.yaml lists (a new machine)")
    o_ = sub.add_parser("override", help="copy a stack's file into your overlay's overrides/ to change it there")
    o_.add_argument("ref", help="<stack>:<path>, e.g. acme:roles/reviewer.md")
    o_.add_argument("--in", dest="root", help="the overlay folder to write in (e.g. its stage worktree)")
    c_ = sub.add_parser("check", help="validate a stack with your overrides in place (L0 + L2); same as psai check <name>")
    c_.add_argument("name")
    d_ = sub.add_parser("diff", help="a stack's change since its pin, or an override against its original")
    d_.add_argument("name")
    d_.add_argument("path", nargs="?")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "add":
            return add(a.src, a.ref, a.as_, a.dev, a.yes)
        if a.cmd == "remove":
            return remove(a.name, a.force)
        if a.cmd == "update":
            return update(a.name, a.to)
        if a.cmd == "list":
            return skills_listing(as_json=a.json) if a.skills else listing(as_json=a.json)
        if a.cmd == "sync":
            return sync_all()
        if a.cmd == "override":
            print(override(a.ref, root=a.root))
            return 0
        if a.cmd == "check":
            return check_stack(a.name)
        if a.cmd == "diff":
            return diff(a.name, a.path)
    except StackError as e:
        print(f"psai stack {a.cmd}: {e}", file=sys.stderr)
        return 1
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(prog="stacks.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["overlay", "migrate-fork", "skill-sources", "packs"])
    ap.add_argument("--home", default=os.environ.get("PSAI_HOME") or os.path.expanduser("~/.psai"))
    ap.add_argument("--clone")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "overlay":
        init_overlay(a.home, a.dry_run)
        return 0
    if a.cmd == "migrate-fork":
        return migrate_fork(a.home, a.clone, a.dry_run)
    if a.cmd == "skill-sources":
        for n, t in skill_sources(a.home):
            print(f"{n}\t{t}")
        return 0
    if a.cmd == "packs":
        for row in packs(a.home):
            print("\t".join(row))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
