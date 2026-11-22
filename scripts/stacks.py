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
"""
import argparse
import os
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
    mine = harness.user_files(clone, layout, [f for f in files if f]) if os.path.exists(layout) else []
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


def skill_sources(home):
    """(name, link target) for every skill psai links, through the home path: the framework's skills/, the overlay's
    my-skills/, each stack's my-skills/, then the fetched skills.yaml packs. The first name wins; clashes go to stderr
    (ADR 0011, section 9.2: PR 7 sharpens who wins)."""
    out, seen = [], {}

    def add(name, target, what):
        if name in seen:
            print(f"skip: {what} {name} clashes with {seen[name]}; rename one of them", file=sys.stderr)
            return
        seen[name] = what
        out.append((name, target))

    _, dirs, packs = skillreg.sources(home)  # paths through the home (framework/, overlay/, stacks/, state/)
    for stack, kind, label, d in dirs:
        for n, _p in skillreg._entries(d):
            add(n, os.path.join(d, n), f"{'psai skills' if stack == 'psai' else label}")
    for stack, sroot, cache in packs:
        for e in skillreg.config(sroot)["skills"]:
            if not isinstance(e, dict) or not e.get("name"):
                continue
            path = str(e.get("path") or ".").strip("/")
            p = os.path.normpath(os.path.join(cache, e["name"], path))
            if os.path.isfile(os.path.join(p, "SKILL.md")):
                add(e["name"], p, f"{stack}:skills.yaml entry")
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
