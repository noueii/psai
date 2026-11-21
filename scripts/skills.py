"""The skill registry: which skills exist, where, which tools see them, and who manages them. Used by harness.py.

Sources psai manages (all in the clone, linked into ~/.claude/skills and ~/.agents/skills by install.sh):
- psai     skills/<name>/              upstream's skills
- my-skills my-skills/<name>/          the user's own skills
- pack     .skills-cache/<name>/<path> a pinned skills.yaml entry, fetched by install.sh (git-ignored)
Folders the tools read (scanned, never written here): the user-level skill folders of each tool and the current
project's. A skill there that isn't a link into the clone, and isn't on skills.yaml's `ignore:` list, is unmanaged:
it's reported, never blocked. `adopt` brings one under psai.

CLI (through harness.py): harness.py skills [list|check|brief|packs|adopt] ...   (see main())
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

import yaml

ROLE_FORBIDDEN = ("request-router", "work")    # a role never routes or starts a workflow
UNPINNED = {"", "main", "master", "head", "latest", "develop", "dev", "trunk", "stable", "default"}
HEX = re.compile(r"^[0-9a-f]{7,40}$")
CACHE = ".skills-cache"

# (label, path relative to HOME, tools that read it). One flat level of <name>/SKILL.md each.
USER_DIRS = [
    ("~/.claude/skills", ".claude/skills", ["claude", "opencode"]),
    ("~/.agents/skills", ".agents/skills", ["opencode", "pi", "omp"]),
    ("~/.config/opencode/skills", "<cfg>/opencode/skills", ["opencode"]),
    ("~/.config/opencode/skill", "<cfg>/opencode/skill", ["opencode"]),
    ("~/.pi/agent/skills", ".pi/agent/skills", ["pi"]),
    ("~/.omp/agent/skills", ".omp/agent/skills", ["omp"]),
]
PROJECT_DIRS = [
    (".claude/skills", ["claude", "opencode"]),
    (".agents/skills", ["opencode", "pi", "omp"]),
    (".opencode/skills", ["opencode"]),
    (".opencode/skill", ["opencode"]),
    (".pi/skills", ["pi"]),
    (".omp/skills", ["omp"]),
]


def _fm(path):
    try:
        text = open(path).read()
    except OSError:
        return {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    try:
        return (yaml.safe_load(m.group(1)) or {}) if m else {}
    except yaml.YAMLError:
        return {}


def use_when(desc):
    """The 'use when ...' part of a description, or the description itself, kept short."""
    d = " ".join(str(desc or "").split())
    m = re.search(r"\bUse (?:it |this skill )?when\b(.*)", d, re.I)
    s = ("use when" + m.group(1)) if m else d
    s = s.rstrip(". ")
    return s if len(s) <= 160 else s[:157].rstrip() + "..."


# ---------- skills.yaml ----------
def config(root):
    """skills.yaml as {skills: [...], ignore: [...]}; missing file = empty."""
    p = os.path.join(root, "skills.yaml")
    if not os.path.exists(p):
        return {"skills": [], "ignore": []}
    c = yaml.safe_load(open(p)) or {}
    return {"skills": c.get("skills") or [], "ignore": c.get("ignore") or []}


def source_url(src):
    src = str(src)
    if src.startswith("github:"):
        return f"https://github.com/{src[len('github:'):].strip('/')}.git"
    return src


def pinned(ref):
    return str(ref or "").strip().lower() not in UNPINNED


def validate_config(root):
    """Format errors in skills.yaml and my-skills/ (no network, no HOME)."""
    errs = []
    p = os.path.join(root, "skills.yaml")
    if os.path.exists(p):
        try:
            c = yaml.safe_load(open(p)) or {}
        except yaml.YAMLError as e:
            return [f"skills.yaml: {e}"]
        if not isinstance(c, dict):
            return ["skills.yaml: must be a mapping with skills: and ignore:"]
        for k in c:
            if k not in ("skills", "ignore"):
                errs.append(f"skills.yaml: unknown key {k!r} (only skills: and ignore:)")
        if not isinstance(c.get("ignore") or [], list):
            errs.append("skills.yaml: ignore: must be a list of names")
        seen = set()
        for i, e in enumerate(c.get("skills") or []):
            if not isinstance(e, dict):
                errs.append(f"skills.yaml: skills[{i}] must be a mapping")
                continue
            n = e.get("name", f"skills[{i}]")
            for k in ("name", "source", "path", "ref"):
                if not e.get(k):
                    errs.append(f"skills.yaml: {n}: missing {k}")
            if e.get("ref") is not None and not pinned(e.get("ref")):
                errs.append(f"skills.yaml: {n}: ref {e.get('ref')!r} is a branch, not pinned (use a tag or a commit)")
            src = str(e.get("source") or "")
            if src and not re.match(r"^(github:[\w.-]+/[\w.-]+|https?://|ssh://|git@|file://|/)", src):
                errs.append(f"skills.yaml: {n}: source must be github:owner/repo or a git URL")
            if n in seen:
                errs.append(f"skills.yaml: {n}: listed twice")
            seen.add(n)
            if os.path.isdir(os.path.join(root, "skills", str(n))) or os.path.isdir(os.path.join(root, "my-skills", str(n))):
                errs.append(f"skills.yaml: {n}: clashes with skills/{n} or my-skills/{n}")
    d = os.path.join(root, "my-skills")
    for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        sd = os.path.join(d, n)
        if not os.path.isdir(sd):
            if n != "README.md":
                errs.append(f"my-skills/{n}: only <name>/SKILL.md folders belong here")
            continue
        md = os.path.join(sd, "SKILL.md")
        if not os.path.exists(md):
            errs.append(f"my-skills/{n}: missing SKILL.md")
            continue
        fm = _fm(md)
        if fm.get("name") != n:
            errs.append(f"my-skills/{n}: name {fm.get('name')!r} != folder")
        if not fm.get("description"):
            errs.append(f"my-skills/{n}: description missing")
        fw = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "skills")
        if os.path.isdir(os.path.join(root, "skills", n)) or os.path.isdir(os.path.join(fw, n)):
            errs.append(f"my-skills/{n}: {n} is reserved by psai's skills/{n} (prefix yours, e.g. my-{n})")
    return errs


def role_skills(path):
    """(required, optional, errors) from a role or step file's `skills:` frontmatter."""
    fm = _fm(path)
    s = fm.get("skills")
    if s is None:
        return [], [], []
    errs = []
    if not isinstance(s, dict) or set(s) - {"required", "optional"}:
        return [], [], ["skills: must be {required: [...], optional: [...]}"]
    req, opt = s.get("required") or [], s.get("optional") or []
    for k, v in (("required", req), ("optional", opt)):
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            errs.append(f"skills.{k} must be a list of skill names")
    for x in (req if isinstance(req, list) else []) + (opt if isinstance(opt, list) else []):
        if x in ROLE_FORBIDDEN:
            errs.append(f"skills: {x} is not for roles (roles never route or run workflows)")
    return list(req) if isinstance(req, list) else [], list(opt) if isinstance(opt, list) else [], errs


# ---------- the registry ----------
def _home():
    return os.path.expanduser("~")


def _cfg(home):
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")


def user_dirs(home=None):
    home = home or _home()
    out = []
    for label, rel, tools in USER_DIRS:
        p = rel.replace("<cfg>", _cfg(home)) if rel.startswith("<cfg>") else os.path.join(home, rel)
        out.append((label, p, tools))
    return out


def project_root(cwd=None):
    cwd = cwd or os.getcwd()
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except OSError:
        pass
    return cwd


def _entries(d):
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return []
    return [(n, os.path.join(d, n)) for n in names
            if not n.startswith(".") and os.path.isfile(os.path.join(d, n, "SKILL.md"))]


def _under(p, root):
    return p == root or p.startswith(root.rstrip("/") + "/")


def sources(root):
    """[(stack, kind, folder label, folder)] psai manages, and [(stack, skills.yaml folder, cache folder)], for the home
    at `root`: the framework's skills/, the overlay's my-skills/ and each installed stack's (resolve.Home)."""
    import resolve  # noqa: PLC0415
    h = resolve.Home(root)
    dirs = [("psai", "psai", "skills/", os.path.join(h.framework, "skills"))]
    dirs.append((resolve.OVERLAY, "my-skills", "my-skills/", os.path.join(h.overlay_path, "my-skills")))
    packs = [(resolve.OVERLAY, h.overlay_path, h.skills_cache(resolve.OVERLAY))]
    for st in h.stacks:
        dirs.append((st.name, "my-skills", f"{st.name}:my-skills/", os.path.join(st.path, "my-skills")))
        packs.append((st.name, st.path, h.skills_cache(st.name)))
    return h, dirs, packs


def registry(root, home=None, project=None):
    """name -> {locations: [...], tools, unmanaged, duplicate, ignored, description}."""
    h, dirs, packs = sources(root)
    roots = {os.path.realpath(p) for p in [root, h.root, h.framework, h.overlay_path, h.state] + [s.path for s in h.stacks]}
    home = home or _home()
    cfg = config(h.overlay_path)
    ignore = set(cfg["ignore"])
    idx = {}

    def add(name, **loc):
        loc["real"] = os.path.realpath(loc["path"])
        idx.setdefault(name, {"locations": []})["locations"].append(loc)

    seen = set()
    for stack, kind, label, d in dirs:
        if os.path.realpath(d) in seen:
            continue
        seen.add(os.path.realpath(d))
        for n, p in _entries(d):
            add(n, where=label, kind=kind, path=p, managed=True, tools=[], stack=stack)
    for stack, sroot, cache in packs:
        for e in config(sroot)["skills"]:
            if not isinstance(e, dict) or not e.get("name"):
                continue
            p = os.path.normpath(os.path.join(cache, e["name"], str(e.get("path") or ".")))
            add(e["name"], where="skills.yaml" if stack == "nostack" else f"{stack}:skills.yaml", kind="pack",
                path=p, managed=True, tools=[], stack=stack,
                fetched=os.path.isfile(os.path.join(p, "SKILL.md")), source=e.get("source"), ref=str(e.get("ref")))
    real_root = os.path.realpath(root)
    for label, d, tools in user_dirs(home):
        for n, p in _entries(d):
            ours = os.path.islink(p) and any(_under(os.path.realpath(p), r) for r in roots)
            add(n, where=label, kind="user", path=p, managed=ours, tools=tools)
    if project and os.path.realpath(project) != real_root:
        for rel, tools in PROJECT_DIRS:
            for n, p in _entries(os.path.join(project, rel)):
                add(n, where=f"<project>/{rel}", kind="project", path=p, managed=False, tools=tools)
    for n, s in idx.items():
        locs = s["locations"]
        s["tools"] = sorted({t for loc in locs for t in loc["tools"]})
        s["ignored"] = n in ignore
        s["unmanaged"] = not s["ignored"] and any(loc["kind"] == "user" and not loc["managed"] for loc in locs)
        reals = {loc["real"] for loc in locs if loc.get("fetched", True)}
        s["duplicate"] = not s["ignored"] and len(reals) > 1
        s["project_only"] = all(loc["kind"] == "project" for loc in locs)
        md = next((os.path.join(loc["path"], "SKILL.md") for loc in locs
                   if os.path.isfile(os.path.join(loc["path"], "SKILL.md"))), None)
        s["description"] = str(_fm(md).get("description", "")) if md else ""
        s["skill_md"] = md
    return idx


def role_files(root):
    out = []
    for d in ("roles", "steps"):
        dd = os.path.join(root, d)
        for f in sorted(os.listdir(dd)) if os.path.isdir(dd) else []:
            if f.endswith(".md") and f != "README.md":
                out.append(os.path.join(dd, f))
    return out


def check(root, home=None, project=None):
    """(errors, warnings, info) for the live setup: roles' skills against the registry."""
    idx = registry(root, home, project)
    errs, warns = [], []
    for f in role_files(root):
        rel = os.path.relpath(f, root)
        req, opt, fe = role_skills(f)
        errs += [f"{rel}: {e}" for e in fe]
        for n in req:
            if n not in idx:
                errs.append(f"{rel}: required skill {n!r} resolves nowhere (install it, or customize-harness adds it)")
            elif idx[n]["project_only"]:
                warns.append(f"{rel}: required skill {n!r} exists only in this project: make it optional")
        for n in opt:
            if n not in idx:
                warns.append(f"{rel}: optional skill {n!r} resolves nowhere (fine; it's noted in the handover)")
    for n, s in sorted(idx.items()):
        if s["duplicate"]:
            where = ", ".join(sorted({loc["where"] for loc in s["locations"]}))
            warns.append(f"skill {n!r} exists in more than one place ({where}): prefix your own skills, e.g. my-{n}")
    unmanaged = sorted(n for n, s in idx.items() if s["unmanaged"])
    return errs, warns, unmanaged


def brief(root, files, shown=None, home=None, project=None):
    """(text, missing_required, missing_optional) for a role agent's brief: role file first, then the step. Each name
    resolves from the stack of the file that lists it (psai resolve: framework, overlay, that stack, its requires,
    then any stack that exports it), so a role always gets its own stack's copy; a skill only the tools have
    (unmanaged, or the project's) comes from the registry."""
    import resolve  # noqa: PLC0415
    shown = shown or root
    h = resolve.Home(root)
    roots = sorted(((os.path.realpath(st.path), st.name) for st in h.content_stacks()), key=lambda x: -len(x[0]))

    def stack_of(f):
        rf = os.path.realpath(f)
        ov = os.path.realpath(os.path.join(h.overlay_path, "overrides"))
        if _under(rf, ov):  # an override: it belongs to the stack it overrides
            return os.path.relpath(rf, ov).split(os.sep)[0]
        return next((n for r, n in roots if _under(rf, r)), resolve.OVERLAY)

    req, opt, frm = [], [], {}
    for f in files:
        r, o, _ = role_skills(f)
        for x in r + o:
            frm.setdefault(x, stack_of(f))
        req += [x for x in r if x not in req]
        opt += [x for x in o if x not in opt]
    opt = [x for x in opt if x not in req]
    idx = None
    have, miss_r, miss_o = [], [], []
    real_root = os.path.realpath(root)
    for n in req + opt:
        md, why = None, ""
        try:
            md = resolve.resolve("skill", n, frm=frm[n], h=h)
        except resolve.ResolveError as e:
            if e.code == resolve.AMBIGUOUS:
                why = f" ({e.msg})"
            else:
                idx = idx if idx is not None else registry(root, home, project)
                md = (idx.get(n) or {}).get("skill_md")
        if not md:
            (miss_r if n in req else miss_o).append(n + why)
            continue
        if _under(os.path.realpath(md), real_root) and h.compat:
            md = os.path.join(shown, os.path.relpath(os.path.realpath(md), real_root))
        have.append(f"{n} ({use_when(_fm(md).get('description')) or 'no description'}; {md})")
    lines = []
    if have:
        lines.append("Your skills: " + "; ".join(have) + ". Invoke each by name when it applies, or read its SKILL.md.")
    else:
        lines.append("Your skills: none listed.")
    if miss_r:
        lines.append("Missing required skills: " + ", ".join(miss_r) + ". Don't start the role: escalate first, "
                     "offering to install them with customize-harness.")
    if miss_o:
        lines.append("Missing optional skills: " + ", ".join(miss_o) + ". Note them in the final report and carry on.")
    return "\n".join(lines), miss_r, miss_o


# ---------- adopt ----------
def _lock(home):
    p = os.path.join(home, ".agents", ".skill-lock.json")
    try:
        return (json.load(open(p)).get("skills") or {})
    except (OSError, ValueError):
        return {}


def _insert_entry(path, entry):
    """Add a skills.yaml entry, keeping the file's comments and layout."""
    block = [f"- name: {entry['name']}", f"  source: {entry['source']}", f"  path: {entry['path']}",
             f"  ref: {entry['ref']}"]
    if not os.path.exists(path):
        text = ("# Skills from other people, pinned. install.sh fetches each into .skills-cache/ and links it.\n"
                "# Format: my-skills/README.md.\nskills:\n" + "\n".join("  " + b for b in block) + "\nignore: []\n")
        open(path, "w").write(text)
        return
    lines = open(path).read().splitlines()
    i = next((k for k, l in enumerate(lines) if re.match(r"^skills:\s*(\[\s*\])?\s*(#.*)?$", l)), None)
    if i is None:
        lines += ["skills:"] + ["  " + b for b in block]
    else:
        if "[" in lines[i]:
            lines[i] = "skills:"
        j, indent = i + 1, None
        while j < len(lines):
            l = lines[j]
            if l.strip() and not l.lstrip().startswith("#") and not l.startswith((" ", "-")):
                break
            if indent is None and l.lstrip().startswith("- "):
                indent = len(l) - len(l.lstrip())
            j += 1
        while j > i + 1 and not lines[j - 1].strip():
            j -= 1
        pad = " " * (2 if indent is None else indent)
        lines[j:j] = [pad + b for b in block]
    open(path, "w").write("\n".join(lines) + "\n")
    got = [e.get("name") for e in config(os.path.dirname(path))["skills"]]
    if entry["name"] not in got:
        raise RuntimeError("could not add the entry to skills.yaml; add it by hand")


def adopt(root, name, home=None, dry=False, ref=None, to=None):
    """Bring an unmanaged skill under psai: the user's own moves into my-skills/, a pack's becomes a pinned
    skills.yaml entry. Returns an exit code; install.sh links the result afterwards."""
    home = home or _home()
    say = (lambda m: print("would: " + m)) if dry else print
    if to:  # into a stack you author (a dev stack) instead of your overlay
        import resolve  # noqa: PLC0415
        st = resolve.Home(root).get(to)
        if st is None or (st.mode not in ("dev", "overlay")):
            print(f"adopt: --to takes your overlay or a dev stack (one you author); {to} is "
                  f"{'not installed' if st is None else st.mode}", file=sys.stderr)
            return 1
        root = st.path
    cfg = config(root)
    if name in cfg["ignore"]:
        print(f"adopt: {name} is on skills.yaml's ignore list (another tool manages it); not adopting", file=sys.stderr)
        return 1
    idx = registry(root, home)
    s = idx.get(name)
    if not s or not any(loc["kind"] == "user" for loc in s["locations"]):
        print(f"adopt: no skill {name!r} in the tool folders", file=sys.stderr)
        return 1
    if not s["unmanaged"]:
        print(f"adopt: {name} is already managed by psai")
        return 0
    if any(loc["kind"] in ("psai", "my-skills", "pack") for loc in s["locations"]):
        print(f"adopt: psai already has a skill named {name}; rename one of them first", file=sys.stderr)
        return 1
    locs = [loc for loc in s["locations"] if loc["kind"] == "user" and not loc["managed"]]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    import resolve  # noqa: PLC0415
    backup = os.path.join(resolve.Home(root).skills_cache(resolve.OVERLAY), ".adopted", f"{name}-{stamp}")
    lk = _lock(home).get(name)
    if lk and (lk.get("sourceUrl") or lk.get("source")):
        src = f"github:{lk['source']}" if lk.get("sourceType") == "github" and lk.get("source") else lk.get("sourceUrl") or lk["source"]
        sub = os.path.dirname(lk.get("skillPath") or "SKILL.md") or "."
        if not ref:
            r = subprocess.run(["git", "ls-remote", source_url(src), "HEAD"], capture_output=True, text=True)
            ref = r.stdout.split()[0] if r.returncode == 0 and r.stdout.split() else None
        if not ref:
            print(f"adopt: can't resolve a commit for {src}; add {name} to skills.yaml by hand with a pinned ref",
                  file=sys.stderr)
            return 1
        say(f"add {name} to skills.yaml (source {src}, path {sub}, ref {ref})")
        if not dry:
            _insert_entry(os.path.join(root, "skills.yaml"), {"name": name, "source": src, "path": sub, "ref": ref})
        for loc in locs:
            if os.path.islink(loc["path"]):
                say(f"unlink {loc['path']}")
                dry or os.remove(loc["path"])
            else:
                say(f"move {loc['path']} -> {backup}/{loc['where'].replace('~/', '').replace('/', '_')}")
                if not dry:
                    os.makedirs(backup, exist_ok=True)
                    shutil.move(loc["path"], os.path.join(backup, loc["where"].replace("~/", "").replace("/", "_")))
        dry or print(f"adopt: {name} is now a pinned skills.yaml entry; npx skills still lists it in ~/.agents/.skill-lock.json")
        return 0
    # the user's own skill
    dest = os.path.join(root, "my-skills", name)
    real_dirs = [loc for loc in locs if not os.path.islink(loc["path"])]
    keep = real_dirs[0] if real_dirs else locs[0]
    if real_dirs:
        say(f"move {keep['path']} -> {dest}")
        dry or shutil.move(keep["path"], dest)
    else:  # only links to a folder outside the tool folders: copy it, leave the original where it is
        say(f"copy {keep['real']} -> {dest} (the original stays)")
        dry or shutil.copytree(keep["real"], dest, symlinks=True)
    for loc in locs:
        if loc is keep and real_dirs:
            continue
        if os.path.islink(loc["path"]):
            say(f"unlink {loc['path']}")
            dry or os.remove(loc["path"])
        else:
            say(f"move duplicate {loc['path']} -> {backup}/")
            if not dry:
                os.makedirs(backup, exist_ok=True)
                shutil.move(loc["path"], os.path.join(backup, loc["where"].replace("~/", "").replace("/", "_")))
    dry or print(f"adopt: {name} moved into my-skills/; commit it in your fork")
    return 0


# ---------- CLI ----------
def _default_root():
    return os.environ.get("PSAI_HOME") or os.path.expanduser("~/.psai")


def main(argv):
    ap = argparse.ArgumentParser(prog="harness.py skills", description="The live skill registry.")
    ap.add_argument("cmd", nargs="?", default="list", choices=["list", "check", "brief", "packs", "adopt"])
    ap.add_argument("args", nargs="*", help="brief: the role file, then the step file; adopt: the skill name")
    ap.add_argument("--root", default=None, help="the psai root (default $PSAI_HOME or ~/.psai)")
    ap.add_argument("--project", default=None, help="the project folder (default: this git repo or cwd)")
    ap.add_argument("--shown", default=None, help="brief: the root as shown in paths (default ~/.psai)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--unmanaged", action="store_true", help="list: only unmanaged skills")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ref", default=None, help="adopt: pin to this ref instead of the source's HEAD")
    ap.add_argument("--to", default=None, help="adopt: into this dev stack (one you author) instead of your overlay")
    a = ap.parse_intermixed_args(argv)
    import resolve  # noqa: PLC0415
    root = resolve.Home(a.root or _default_root()).overlay_path  # the user's skills and skills.yaml live in the overlay
    project = a.project or project_root()

    if a.cmd == "packs":  # for install.sh: name, url, path, ref (tab-separated), pinned entries only
        for e in config(root)["skills"]:
            if isinstance(e, dict) and all(e.get(k) for k in ("name", "source", "path", "ref")):
                if pinned(e["ref"]):
                    print("\t".join([e["name"], source_url(e["source"]), str(e["path"]), str(e["ref"])]))
                else:
                    print(f"skip: skills.yaml entry {e['name']} is not pinned (ref {e['ref']})", file=sys.stderr)
        return 0
    if a.cmd == "adopt":
        if len(a.args) != 1:
            ap.error("adopt takes one skill name")
        if os.environ.get("PSAI_EVAL") and not a.dry_run:
            print("psai: eval run: adopt never moves skills out of the real HOME", file=sys.stderr)
            return 1
        return adopt(root, a.args[0], dry=a.dry_run, ref=a.ref, to=a.to)
    if a.cmd == "brief":
        if not a.args:
            ap.error("brief takes the role file (and the step file)")
        text, miss_r, _ = brief(root, a.args, a.shown or ("~/.psai" if not os.environ.get("PSAI_HOME") else root),
                                project=project)
        print(text)
        return 3 if miss_r else 0
    if a.cmd == "check":
        errs, warns, unmanaged = check(root, project=project)
        errs = errs + validate_config(root)
        if a.json:
            print(json.dumps({"errors": errs, "warnings": warns, "unmanaged": unmanaged}, indent=1))
        else:
            for e in errs:
                print("  FAIL", e)
            for w in warns:
                print("  warn", w)
            print(f"  info {len(unmanaged)} unmanaged skill(s) in your tool folders"
                  + (f": {', '.join(unmanaged)} (adopt with customize-harness or install.sh --adopt <name>)" if unmanaged else ""))
        return 1 if errs else 0
    idx = registry(root, project=project)
    if a.unmanaged:
        idx = {n: s for n, s in idx.items() if s["unmanaged"]}
    if a.json:
        print(json.dumps(idx, indent=1, sort_keys=True))
        return 0
    for n, s in sorted(idx.items()):
        flags = [f for f in ("unmanaged", "duplicate", "ignored") if s[f]]
        where = ", ".join(dict.fromkeys(loc["where"] for loc in s["locations"]))
        stk = ",".join(dict.fromkeys(loc["stack"] for loc in s["locations"] if loc.get("stack"))) or "-"
        print(f"{n:32} {stk:16} {','.join(s['tools']) or '-':24} {where}" + (f"  [{' '.join(flags)}]" if flags else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
