#!/usr/bin/env python3
"""psai build --standalone (ADR 0011, section 13): one stack plus a pinned copy of the framework, as a native package
per tool, for people who don't install psai.

  psai build --standalone [<stack>|<path>] [--target claude] [--out dist] [--check]

A bundle is itself a psai home: `framework/` (the runtime, at this framework's version), `stacks/<name>/` (the stack's
content), `bundle.yaml` (what was built), and an `overlay/` and `state/` created on first use. In a bundle, PSAI_HOME
is the bundle (the `psai` there finds it on its own), stack management is disabled, and the retro's suggestions go to
the stack's author.
  claude   dist/<name>/claude/: .claude-plugin/plugin.json, hooks/ (the SessionStart/SubagentStart/SessionEnd hooks of
           plugins/claude, pointed at the bundle), skills/ (the framework's and the stack's own), and the home above;
           plus dist/<name>/.claude-plugin/marketplace.json, so `claude plugin marketplace add <dist/name>` works.
--check builds into a temp folder and exits 1 when the committed dist/ differs (stack.yaml `build.commit_dist`).
"""
import argparse
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import resolve as res  # noqa: E402

FW = os.path.dirname(HERE)
TARGETS = ("claude",)
RUNTIME = ("scripts", "skills", "instructions", "schemas", "template", "VERSION", "LAYOUT.md")
IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "dist", "results", ".state", ".skills-cache")


class BuildError(Exception):
    pass


def tracked(path):
    """The stack's files: git's tracked and untracked-but-not-ignored files, else everything."""
    p = subprocess.run(["git", "-C", path, "ls-files", "-co", "--exclude-standard", "-z"], capture_output=True, text=True)
    if p.returncode:
        return None
    return sorted(f for f in p.stdout.split("\0") if f)


def copy_stack(src, dest):
    files = tracked(src)
    if files is None:
        shutil.copytree(src, dest, ignore=IGNORE)
        return
    for f in files:
        if f.split("/")[0] in ("dist", ".github") or f.startswith("evals/results/"):
            continue
        d = os.path.join(dest, f)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(os.path.join(src, f), d)


def make_home(dest, src, meta):
    """The bundle as a psai home: the framework runtime, the stack, and bundle.yaml."""
    fw = os.path.join(dest, "framework")
    os.makedirs(fw)
    for x in RUNTIME:
        s = os.path.join(FW, x)
        (shutil.copytree if os.path.isdir(s) else shutil.copy2)(s, os.path.join(fw, x), **({"ignore": IGNORE} if os.path.isdir(s) else {}))
    copy_stack(src, os.path.join(dest, "stacks", meta["name"]))
    with open(os.path.join(dest, "bundle.yaml"), "w") as f:
        yaml.safe_dump({"standalone": True, "stack": meta["name"], "version": str(meta.get("version")),
                        "psai": res.framework_version(FW)}, f, sort_keys=False)


def skills_into(dest, src):
    """The tool-visible skills: the framework's, then the stack's own (a clash with a reserved name is refused)."""
    os.makedirs(dest, exist_ok=True)
    for base in (os.path.join(FW, "skills"), os.path.join(src, "my-skills")):
        for n in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            if not os.path.isfile(os.path.join(base, n, "SKILL.md")):
                continue
            if os.path.exists(os.path.join(dest, n)):
                raise BuildError(f"my-skills/{n} uses a name psai reserves; rename it")
            shutil.copytree(os.path.join(base, n), os.path.join(dest, n), ignore=IGNORE)


def build_claude(out, src, meta):
    name = meta["name"]
    p = os.path.join(out, name, "claude")
    make_home(p, src, meta)
    os.makedirs(os.path.join(p, ".claude-plugin"))
    desc = " ".join(str(meta.get("description", "")).split())
    with open(os.path.join(p, ".claude-plugin", "plugin.json"), "w") as f:
        json.dump({"name": name, "version": str(meta.get("version")), "description": desc + " (a psai stack, standalone)",
                   "author": {"name": (meta.get("author") or {}).get("name") or name}}, f, indent=2)
        f.write("\n")
    os.makedirs(os.path.join(p, "hooks"))
    for h in ("session-start.sh", "session-end.sh"):
        shutil.copy2(os.path.join(FW, "plugins", "claude", "hooks", h), os.path.join(p, "hooks", h))
    root = '${CLAUDE_PLUGIN_ROOT}'
    init = f'python3 "{root}/framework/scripts/stacks.py" overlay --home "{root}" >/dev/null 2>&1; '
    cmd = lambda script, arg="": (f'{init}PSAI_HOME="{root}" bash "{root}/hooks/{script}"' + (f" {arg}" if arg else ""))
    hooks = {"hooks": {
        "SessionStart": [{"matcher": "startup|resume|clear|compact",
                          "hooks": [{"type": "command", "command": cmd("session-start.sh", "SessionStart")}]}],
        "SubagentStart": [{"hooks": [{"type": "command", "command": cmd("session-start.sh", "SubagentStart")}]}],
        "SessionEnd": [{"hooks": [{"type": "command", "command": cmd("session-end.sh")}]}]}}
    with open(os.path.join(p, "hooks", "hooks.json"), "w") as f:
        json.dump(hooks, f, indent=2)
        f.write("\n")
    skills_into(os.path.join(p, "skills"), src)
    mk = os.path.join(out, name, ".claude-plugin")
    os.makedirs(mk, exist_ok=True)
    author = (meta.get("author") or {}).get("name") or name
    with open(os.path.join(mk, "marketplace.json"), "w") as f:
        json.dump({"name": name, "owner": {"name": author}, "description": desc,
                   "plugins": [{"name": name, "source": "./claude", "description": desc}]}, f, indent=2)
        f.write("\n")
    return p


BUILDERS = {"claude": build_claude}


def stack_path(ref):
    if not ref:
        ref = "."
    if os.path.isdir(ref) and os.path.exists(os.path.join(ref, "stack.yaml")):
        return os.path.abspath(ref)
    st = res.home().get(ref)
    if st is None or st.name in res.RESERVED:
        raise BuildError(f"no stack {ref!r} (a folder with a stack.yaml, or an installed stack's name)")
    return st.path


def build(ref=None, targets=TARGETS, out="dist"):
    src = stack_path(ref)
    meta = res.load_stack(src)
    errs = res.validate_stack(meta)
    if errs:
        raise BuildError("stack.yaml: " + "; ".join(errs))
    for t in targets:
        if t not in BUILDERS:
            raise BuildError(f"unknown target {t!r} (this psai builds: {', '.join(BUILDERS)})")
    dest = os.path.join(out, meta["name"])
    if os.path.exists(dest):
        shutil.rmtree(dest)
    built = [BUILDERS[t](out, src, meta) for t in targets]
    return meta, built


def same_tree(a, b):
    c = filecmp.dircmp(a, b)
    if c.left_only or c.right_only or c.funny_files:
        return False
    if filecmp.cmpfiles(a, b, c.common_files, shallow=False)[1:] != ([], []):
        return False
    return all(same_tree(os.path.join(a, d), os.path.join(b, d)) for d in c.common_dirs)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="psai build", description=__doc__.split("\n\n")[0])
    ap.add_argument("stack", nargs="?", help="a stack folder or an installed stack (default: this folder)")
    ap.add_argument("--standalone", action="store_true", help="required: build packages that need no psai install")
    ap.add_argument("--target", default=",".join(TARGETS), help=f"comma-separated: {', '.join(TARGETS)}")
    ap.add_argument("--out", default=None, help="the output folder (default: <stack>/dist)")
    ap.add_argument("--check", action="store_true", help="exit 1 when the committed dist/ is stale")
    a = ap.parse_args(argv)
    if not a.standalone:
        ap.error("only --standalone builds exist")
    targets = [t.strip() for t in a.target.split(",") if t.strip()]
    try:
        src = stack_path(a.stack)
        out = a.out or os.path.join(src, "dist")
        if a.check:
            with tempfile.TemporaryDirectory() as t:
                meta, _ = build(src, targets, t)
                have = os.path.join(out, meta["name"])
                if not os.path.isdir(have) or not same_tree(os.path.join(t, meta["name"]), have):
                    print(f"psai build: {have} is stale; run psai build --standalone and commit it", file=sys.stderr)
                    return 1
            print("psai build: dist/ is up to date")
            return 0
        meta, built = build(src, targets, out)
    except BuildError as e:
        print(f"psai build: {e}", file=sys.stderr)
        return 1
    for b in built:
        print(f"psai build: {meta['name']} {meta.get('version')} -> {b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
