#!/usr/bin/env python3
"""psai build --standalone (ADR 0011, section 13): one stack plus a pinned copy of the framework, as a native package
per tool, for people who don't install psai.

  psai build --standalone [<stack>|<path>] [--target claude] [--out dist] [--check]

A bundle is itself a psai home: `framework/` (the runtime, at this framework's version), `stacks/<name>/` (the stack's
content), `bundle.yaml` (what was built), and an `overlay/` and `state/` created on first use. In a bundle, PSAI_HOME
is the bundle (the `psai` there finds it on its own), stack management is disabled, and the retro's suggestions go to
the stack's author.
  claude          dist/<name>/claude/: .claude-plugin/plugin.json, hooks/ (plugins/claude's, pointed at the bundle),
                  skills/ (the framework's and the stack's own) and the home above; plus
                  dist/<name>/.claude-plugin/marketplace.json (`claude plugin marketplace add <dist/name>`).
  agent-plugins   dist/<name>/agent-plugins/: the open plugin format Cursor reads (.cursor-plugin/plugin.json, skills/,
                  rules/psai.mdc: the nudge as an always-applied rule, built from the bundle); plus
                  dist/<name>/.cursor-plugin/marketplace.json.
  pi              dist/<name>/pi/: a pi package (package.json `pi`: extensions/psai.ts, skills/); `pi install <dir>`.
  omp             dist/<name>/omp/: an omp plugin (package.json `omp`: extensions/psai.ts; skills/); `omp plugin
                  install <dir>`, or `--plugin-dir`.
  opencode        dist/<name>/opencode/: install.sh (--dry-run, --uninstall) writes a stub plugin into
                  ~/.config/opencode/plugin/ and links the skills into ~/.config/opencode/skills/.
The pi, omp and opencode extensions are plugins/<tool>'s, with their one bootstrap pointed at the bundle.
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
TARGETS = ("claude", "agent-plugins", "pi", "omp", "opencode")
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


def bundled_extension(tool, dest):
    """plugins/<tool>'s extension with its one bootstrap pointed at the bundle it ships in (one folder up), creating
    the bundle's overlay on first use."""
    ext = "psai.js" if tool == "opencode" else "psai.ts"
    text = open(os.path.join(FW, "plugins", tool, ext)).read()
    ts = ": string" if ext.endswith(".ts") else ""
    pairs = [
        ('import { join } from "node:path";\n',
         'import { join } from "node:path";\nimport { fileURLToPath } from "node:url";\n'),
        ('  return process.env.PSAI_HOME || join(homedir(), ".psai"); // psai-bootstrap',
         '  return join(fileURLToPath(new URL(".", import.meta.url)), ".."); // psai-bootstrap: the bundle this file ships in'),
        ('  const shown = process.env.PSAI_HOME ? home() : "~/.psai";', '  const shown = home();'),
        (f'function psai(){ts} {{\n',
         f'function psai(){ts} {{\n  if (!existsSync(join(home(), "overlay"))) {{ // the bundle\'s overlay, made on first use\n'
         f'    try {{ execFileSync("python3", [join(home(), "framework", "scripts", "stacks.py"), "overlay", "--home", home()], '
         f'{{ stdio: "ignore" }}); }} catch {{}}\n  }}\n'),
    ]
    for a, b in pairs:
        if a not in text:
            raise BuildError(f"plugins/{tool}/{ext} changed: can't point its bootstrap at the bundle ({a.strip()[:40]})")
        text = text.replace(a, b)
    text = f"// Built by psai build --standalone from plugins/{tool}/{ext}; its home is this bundle.\n" + text
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as f:
        f.write(text)


def nudge(home, shown):
    """The nudge as the bundle would inject it, for targets that take static text (an always-applied rule)."""
    p = subprocess.run([sys.executable, os.path.join(home, "framework", "scripts", "harness.py"), "context", home, shown],
                       capture_output=True, text=True, env=dict(os.environ, PSAI_HOME=home, PSAI_STATE=os.path.join(
                           tempfile.mkdtemp(), "state"), HOME=tempfile.mkdtemp()))
    if p.returncode:
        raise BuildError(f"can't render the nudge: {p.stderr.strip()[-300:]}")
    return p.stdout


def build_agent_plugins(out, src, meta):
    name = meta["name"]
    p = os.path.join(out, name, "agent-plugins")
    make_home(p, src, meta)
    desc = " ".join(str(meta.get("description", "")).split())
    author = {"name": (meta.get("author") or {}).get("name") or name}
    os.makedirs(os.path.join(p, ".cursor-plugin"))
    m = {"name": name, "version": str(meta.get("version")), "description": desc + " (a psai stack, standalone)",
         "author": author, "skills": "./skills/", "rules": "./rules/"}
    if meta.get("license"):
        m["license"] = meta["license"]
    with open(os.path.join(p, ".cursor-plugin", "plugin.json"), "w") as f:
        json.dump(m, f, indent=2)
        f.write("\n")
    skills_into(os.path.join(p, "skills"), src)
    os.makedirs(os.path.join(p, "rules"))
    text = nudge(p, "<this plugin's folder>")
    with open(os.path.join(p, "rules", "psai.mdc"), "w") as f:
        f.write(f"---\ndescription: psai: route every request through the {name} stack's workflows\nalwaysApply: true\n---\n"
                + text)
    mk = os.path.join(out, name, ".cursor-plugin")
    os.makedirs(mk, exist_ok=True)
    with open(os.path.join(mk, "marketplace.json"), "w") as f:
        json.dump({"name": name, "owner": author, "metadata": {"description": desc},
                   "plugins": [{"name": name, "source": "./agent-plugins", "description": desc}]}, f, indent=2)
        f.write("\n")
    return p


def _package_json(p, meta, key, manifest):
    name = meta["name"]
    pkg = {"name": f"psai-{name}", "version": str(meta.get("version")), "type": "module",
           "description": " ".join(str(meta.get("description", "")).split()) + " (a psai stack, standalone)",
           "keywords": [f"{key}-package" if key == "pi" else "omp-plugin", "psai"], key: manifest}
    if meta.get("license"):
        pkg["license"] = meta["license"]
    with open(os.path.join(p, "package.json"), "w") as f:
        json.dump(pkg, f, indent=2)
        f.write("\n")


def build_pi(out, src, meta):
    p = os.path.join(out, meta["name"], "pi")
    make_home(p, src, meta)
    bundled_extension("pi", os.path.join(p, "extensions", "psai.ts"))
    skills_into(os.path.join(p, "skills"), src)
    _package_json(p, meta, "pi", {"extensions": ["./extensions/psai.ts"], "skills": ["./skills"]})
    return p


def build_omp(out, src, meta):
    p = os.path.join(out, meta["name"], "omp")
    make_home(p, src, meta)
    bundled_extension("omp", os.path.join(p, "extensions", "psai.ts"))
    skills_into(os.path.join(p, "skills"), src)
    _package_json(p, meta, "omp", {"name": meta["name"], "version": str(meta.get("version")),
                                   "extensions": ["./extensions/psai.ts"]})
    return p


OPENCODE_INSTALL = """#!/usr/bin/env bash
# Install the __NAME__ stack (a psai standalone build) for opencode: a stub plugin that imports this bundle's plugin,
# and links to its skills. Idempotent. Usage: ./install.sh [--dry-run] [--uninstall]
set -euo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CFG="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
MARK="// psai __NAME__: managed by its install.sh"
STUB="$CFG/plugin/psai-__NAME__.js"
DRY=0; MODE=install
for a in "$@"; do case "$a" in --dry-run) DRY=1 ;; --uninstall) MODE=uninstall ;; *) echo "unknown option: $a" >&2; exit 2 ;; esac; done
say() { if [ "$DRY" = 1 ]; then echo "would: $*"; else echo "$*"; fi; }
do_() { [ "$DRY" = 1 ] || "$@"; }
[ -d "$CFG" ] || { echo "opencode isn't set up here ($CFG missing)" >&2; exit 1; }
if [ "$MODE" = install ]; then
  if [ -e "$STUB" ] && ! grep -Fxq "$MARK" "$STUB"; then echo "skip: $STUB exists and is not ours" >&2
  else
    new="$(printf '%s\\nexport { Psai } from "%s/plugin/psai.js";\\n' "$MARK" "$B")"
    if [ "$(cat "$STUB" 2>/dev/null)" != "$(printf "$new")" ]; then say "write $STUB"; do_ mkdir -p "$CFG/plugin"; [ "$DRY" = 1 ] || printf "$new" > "$STUB"; fi
  fi
  for s in "$B"/skills/*/; do
    n="$(basename "$s")"; t="$CFG/skills/$n"
    if [ -L "$t" ] && [ "$(readlink "$t")" = "${s%/}" ]; then continue; fi
    if [ -e "$t" ] || [ -L "$t" ]; then echo "skip: $t exists and is not ours" >&2; continue; fi
    say "link $t -> ${s%/}"; do_ mkdir -p "$CFG/skills"; do_ ln -s "${s%/}" "$t"
  done
else
  if [ -f "$STUB" ] && grep -Fxq "$MARK" "$STUB"; then say "remove $STUB"; do_ rm -f "$STUB"; fi
  for t in "$CFG"/skills/*; do
    if [ -L "$t" ] && case "$(readlink "$t")" in "$B"/*) true ;; *) false ;; esac; then say "unlink $t"; do_ rm -f "$t"; fi
  done
fi
echo "psai __NAME__: $MODE done$([ "$DRY" = 1 ] && echo ' (dry run)')"
"""


def build_opencode(out, src, meta):
    p = os.path.join(out, meta["name"], "opencode")
    make_home(p, src, meta)
    bundled_extension("opencode", os.path.join(p, "plugin", "psai.js"))
    skills_into(os.path.join(p, "skills"), src)
    with open(os.path.join(p, "install.sh"), "w") as f:
        f.write(OPENCODE_INSTALL.replace("__NAME__", meta["name"]))
    os.chmod(os.path.join(p, "install.sh"), 0o755)
    return p


BUILDERS = {"claude": build_claude, "agent-plugins": build_agent_plugins, "pi": build_pi, "omp": build_omp,
            "opencode": build_opencode}


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
