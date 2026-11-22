#!/usr/bin/env python3
"""psai resolve: find content by name across the framework, the installed stacks and the overlay (ADR 0011, section 5).

  psai resolve <kind> <ref> [--from <stack>] [--all] [--json] [--write]
  psai resolve <ref>                      # kind taken from the path, e.g. acme:roles/reviewer.md
  kinds: workflow role step guide template skill knowledge file instructions

A ref is `[stack:]<path inside the stack>`, or a short name where the kind says the folder (`role reviewer`,
`workflow acme:review`, `skill change-notes`). A bare ref means the stack given by --from (the stack whose file holds
it); with no --from, the overlay `nostack` if it has the file, else the one installed stack that has it.

Layers, highest first: the overlay's override `overlay/overrides/<stack>/<path>`, then the stack itself. Knowledge is
never overridden: it is additive (the stack's curated file, then `overlay/knowledge/<stack>/<path>`), and --all lists
both. --write prints where a write for the ref belongs instead of the winner: the overlay for the overlay's own files
and for every knowledge inbox, an override in the overlay for a pinned stack, the clone itself for a dev stack.

Exit codes: 0 found; 3 not found; 4 not exported (a cross-stack ref to a name its stack doesn't export); 5 ambiguous
(a bare name two candidates at the same level have).

The home (`$PSAI_HOME`, else ~/.psai):
- stacks layout: framework/ (the psai clone), overlay/ (the stack `nostack`, with stacks.yaml listing the installed
  stacks), stacks/<name>/ (each installed stack), state/;
- single-root compat mode (no framework/ folder: today's fork clone, or any content root such as a test fixture): the
  home is the stack `nostack` and the framework is the clone this script runs from. Behaviour is unchanged.

Python API: home(), resolve(kind, ref, frm=None), resolve_all(...), write_target(...), load_stack(path),
validate_stack(meta), in_range(version, spec).
"""
import argparse
import json
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
FRAMEWORK = os.path.dirname(HERE)
RESERVED = ("psai", "nostack")
OVERLAY = "nostack"
NAME_RX = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
REF_RX = re.compile(r"^([a-z][a-z0-9-]{1,31}):(.+)$")
FOUND, NOT_FOUND, NOT_EXPORTED, AMBIGUOUS = 0, 3, 4, 5

# kind -> (folder, extension); skill, file and knowledge are special
KINDS = {
    "workflow": ("workflows", ".yaml"),
    "role": ("roles", ".md"),
    "step": ("steps", ".md"),
    "guide": ("guides", ".md"),
    "template": ("templates", ".md"),
    "instructions": ("instructions", ".md"),
    "knowledge": ("knowledge", ""),
    "skill": ("my-skills", ""),
    "file": ("", ""),
}
FOLDER_KIND = {v[0]: k for k, v in KINDS.items() if v[0]}
EXPORTABLE = ("workflows", "roles", "steps", "guides", "templates", "skills")


class ResolveError(Exception):
    def __init__(self, code, msg, candidates=None):
        super().__init__(msg)
        self.code, self.msg, self.candidates = code, msg, candidates or []


# ---------- versions ----------
def _vt(v):
    m = re.match(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(v).strip())
    if not m:
        raise ValueError(f"not a version: {v!r}")
    return tuple(int(x or 0) for x in m.groups())


def parse_range(spec):
    """'>=3.0 <4' -> [(op, tuple)]; raises ValueError on a bad range."""
    out = []
    for part in str(spec).replace(",", " ").split():
        m = re.match(r"^(>=|<=|==|=|>|<|\^|~)?(v?\d+(?:\.\d+){0,2})$", part)
        if not m:
            raise ValueError(f"bad version range {spec!r} (use comparators such as '>=3.0 <4')")
        op, v = m.group(1) or "==", _vt(m.group(2))
        if op == "^":
            out += [(">=", v), ("<", (v[0] + 1, 0, 0))]
        elif op == "~":
            out += [(">=", v), ("<", (v[0], v[1] + 1, 0))]
        else:
            out.append(("==" if op == "=" else op, v))
    if not out:
        raise ValueError("empty version range")
    return out


def in_range(version, spec):
    v = _vt(version)
    ops = {">=": v.__ge__, "<=": v.__le__, ">": v.__gt__, "<": v.__lt__, "==": v.__eq__}
    return all(ops[op](t) for op, t in parse_range(spec))


def framework_version(fw=FRAMEWORK):
    try:
        return open(os.path.join(fw, "VERSION")).read().strip()
    except OSError:
        return "0.0.0"


# ---------- stack.yaml ----------
def load_stack(path):
    """A stack's stack.yaml as a dict ({} when it has none, as a compat root)."""
    p = os.path.join(path, "stack.yaml")
    if not os.path.exists(p):
        return {}
    with open(p) as f:
        return yaml.safe_load(f) or {}


def _schema():
    with open(os.path.join(FRAMEWORK, "schemas", "stack.schema.json")) as f:
        return json.load(f)


def _check(node, val, where, root, errs):
    """The subset of JSON Schema stack.schema.json uses, plus maxWords and format: version-range."""
    if "$ref" in node:
        node = root["$defs"][node["$ref"].split("/")[-1]]
    if "oneOf" in node:
        ok = [o for o in node["oneOf"] if not _check(o, val, where, root, [])]
        if len(ok) != 1:
            errs.append(f"{where}: does not match any allowed form")
        return errs
    t = node.get("type")
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}
    if t and (not isinstance(val, types[t]) or (t == "integer" and isinstance(val, bool))):
        errs.append(f"{where}: must be a{'n' if t[0] in 'aeiou' else ''} {t}")
        return errs
    if "enum" in node and val not in node["enum"]:
        errs.append(f"{where}: must be one of {', '.join(map(str, node['enum']))}")
    if "pattern" in node and not re.match(node["pattern"], val):
        errs.append(f"{where}: {val!r} doesn't match {node['pattern']}")
    if "maxWords" in node and len(val.split()) > node["maxWords"]:
        errs.append(f"{where}: over {node['maxWords']} words")
    if node.get("format") == "version-range":
        try:
            parse_range(val)
        except ValueError as e:
            errs.append(f"{where}: {e}")
    if t == "object":
        for k in node.get("required", []):
            if k not in val:
                errs.append(f"{where}: missing {k}")
        props = node.get("properties", {})
        for k, v in val.items():
            if k in props:
                _check(props[k], v, f"{where}.{k}", root, errs)
            elif node.get("additionalProperties") is False:
                errs.append(f"{where}: unknown key {k!r}")
    if t == "array" and "items" in node:
        for i, v in enumerate(val):
            _check(node["items"], v, f"{where}[{i}]", root, errs)
    return errs


def validate_stack(meta, overlay=False):
    """Errors in a stack.yaml dict: the schema, reserved names, overlay-only keys."""
    if not isinstance(meta, dict):
        return ["stack.yaml: must be a mapping"]
    sch = _schema()
    errs = _check(sch, meta, "stack.yaml", sch, [])
    name = meta.get("name")
    if overlay and name != OVERLAY:
        errs.append(f"stack.yaml: the overlay's name must be {OVERLAY}")
    if not overlay and name in RESERVED:
        errs.append(f"stack.yaml: name {name!r} is reserved (psai, nostack)")
    import models  # noqa: PLC0415
    m = meta.get("models") or {}
    if isinstance(m, dict):
        if "default" in m:
            errs += models.validate(m["default"], "stack.yaml.models.default")
        for k, v in (m.get("roles") or {}).items():
            errs += models.validate(v, f"stack.yaml.models.roles.{k}")
    if not overlay:
        for k in ("disable", "prefer", "priority"):
            if k in meta:
                errs.append(f"stack.yaml: {k}: only the overlay ({OVERLAY}) sets it")
    return errs


# ---------- the home ----------
class Stack:
    def __init__(self, name, path, mode, meta=None, entry=None, order=0):
        self.name, self.path, self.mode, self.order = name, path, mode, order
        self.meta = meta if meta is not None else load_stack(path)
        self.entry = entry or {}

    @property
    def priority(self):
        return int(((self.meta.get("routing") or {}).get("priority")) or 50)

    def exports(self, folder):
        if self.name in RESERVED:
            return "*"
        e = (self.meta.get("exports") or {}).get(folder)
        return e if e == "*" else list(e or [])

    def __repr__(self):
        return f"Stack({self.name}, {self.path}, {self.mode})"


def bundle_home():
    """The bundle this framework runs from (`psai build --standalone`: framework/ next to bundle.yaml), or None."""
    parent = os.path.dirname(FRAMEWORK)
    return parent if os.path.basename(FRAMEWORK) == "framework" and os.path.exists(os.path.join(parent, "bundle.yaml")) else None


def default_root():
    return os.environ.get("PSAI_HOME") or bundle_home() or os.path.expanduser("~/.psai")


class Home:
    def __init__(self, root=None):
        self.root = os.path.abspath(root or default_root())
        if os.path.basename(self.root) == "overlay" and os.path.isdir(os.path.join(os.path.dirname(self.root), "framework")):
            self.root = os.path.dirname(self.root)  # given the overlay: its home
        self.compat = not os.path.isdir(os.path.join(self.root, "framework"))
        if self.compat:
            self.framework = FRAMEWORK
            self.overlay_path = self.root
            self.state = os.environ.get("PSAI_STATE") or os.path.join(self.root, ".state")
        else:
            self.framework = os.path.join(self.root, "framework")
            self.overlay_path = os.path.join(self.root, "overlay")
            self.state = os.environ.get("PSAI_STATE") or os.path.join(self.root, "state")
        self.overlay = Stack(OVERLAY, self.overlay_path, "overlay")
        self.psai = Stack("psai", self.framework, "framework", meta={})
        self.stacks = []
        for i, e in enumerate(self.entries()):
            n = e.get("name")
            if not n or n in RESERVED:
                continue
            p = os.path.join(self.root, "stacks", n)
            self.stacks.append(Stack(n, p, e.get("mode", "pinned"), entry=e, order=i))

    @property
    def bundle(self):
        """bundle.yaml of a standalone build (ADR 0011, section 13), else {}."""
        try:
            with open(os.path.join(self.root, "bundle.yaml")) as f:
                return yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            return {}

    def entries(self):
        """overlay/stacks.yaml's `stacks:` list (empty in compat mode); a bundle's stack is always there."""
        if self.compat:
            return []
        out = []
        p = os.path.join(self.overlay_path, "stacks.yaml")
        if os.path.exists(p):
            with open(p) as f:
                out = (yaml.safe_load(f) or {}).get("stacks") or []
        b = self.bundle.get("stack")
        if b and not any(e.get("name") == b for e in out):
            out.insert(0, {"name": b, "mode": "bundled", "version": str(self.bundle.get("version"))})
        return out

    def get(self, name):
        if name == OVERLAY:
            return self.overlay
        if name == "psai":
            return self.psai
        for s in self.stacks:
            if s.name == name:
                return s
        return None

    def content_stacks(self):
        """The overlay, then the installed stacks in stacks.yaml order."""
        return [self.overlay] + self.stacks

    def skills_cache(self, stack):
        if self.compat:
            return os.path.join(self.overlay_path, ".skills-cache")
        return os.path.join(self.state, "skills-cache", stack)


def home(root=None):
    return Home(root)


# ---------- refs ----------
def split_ref(ref):
    """'acme:roles/x.md' -> ('acme', 'roles/x.md'); 'roles/x.md' -> (None, 'roles/x.md')."""
    m = REF_RX.match(str(ref))
    return (m.group(1), m.group(2)) if m else (None, str(ref))


def rel_path(kind, rest):
    """The path inside a stack for a kind and a ref without its stack prefix."""
    rest = rest.lstrip("/")
    if kind == "file":
        return rest
    if kind == "skill":
        return rest.split("/")[-2] if rest.endswith("/SKILL.md") else rest.rstrip("/").split("/")[-1]
    folder, ext = KINDS[kind]
    if not rest.startswith(folder + "/"):
        rest = f"{folder}/{rest}"
    if ext and not rest.endswith(ext):
        rest += ext
    return rest


def kind_of(path):
    first = path.lstrip("/").split("/")[0]
    return FOLDER_KIND.get(first, "file") if first != "my-skills" else "skill"


def _export_name(path):
    """('guides', 'style') for guides/style.md; (None, None) for paths outside an exportable folder."""
    parts = path.split("/")
    folder = "skills" if parts[0] == "my-skills" else parts[0]
    if folder not in EXPORTABLE or len(parts) < 2:
        return None, None
    name = parts[1]
    for ext in (".yaml", ".md"):
        if name.endswith(ext):
            name = name[: -len(ext)]
    return folder, name


def exported(stack, path):
    folder, name = _export_name(path)
    if folder is None:
        return stack.name in RESERVED
    e = stack.exports(folder)
    return e == "*" or name in e


def _layers(h, stack, path, knowledge=False):
    """[(layer, abs path)] for one stack's file, highest first, existing or not."""
    out = []
    if stack.name not in RESERVED and not knowledge:
        out.append((OVERLAY, os.path.join(h.overlay_path, "overrides", stack.name, path)))
    out.append((stack.name, os.path.join(stack.path, path)))
    if knowledge and stack.name not in RESERVED:
        out.append((OVERLAY, os.path.join(h.overlay_path, "knowledge", stack.name, path[len("knowledge/"):])))
    return out


def _result(h, kind, stack, path, layers, frm):
    found = [(layer, p) for layer, p in layers if os.path.exists(p)]
    layer, p = found[0]
    return {"stack": stack.name, "kind": kind, "name": path, "path": p, "layer": layer,
            "overridden_by": OVERLAY if layer == OVERLAY and kind != "knowledge" else None,
            "exported": exported(stack, path), "layers": [x for _, x in found], "from": frm}


def _check_export(stack, path, frm):
    if frm and frm != stack.name and frm != OVERLAY and not exported(stack, path):
        raise ResolveError(NOT_EXPORTED, f"{stack.name}:{path} is not exported by {stack.name} (stack.yaml exports), "
                                         f"so {frm} can't reference it")


def _skill_dirs(h, stack, name, packs=True):
    """Where stack `stack` may hold skill `name`, in order: framework skills/, my-skills/, its skills.yaml packs."""
    if stack.name == "psai":
        return [os.path.join(stack.path, "skills", name)]
    out = [os.path.join(h.overlay_path, "overrides", stack.name, "my-skills", name)] if stack.name != OVERLAY else []
    out.append(os.path.join(stack.path, "my-skills", name))
    if not packs:
        return out
    try:
        with open(os.path.join(stack.path, "skills.yaml")) as f:
            for e in (yaml.safe_load(f) or {}).get("skills") or []:
                if isinstance(e, dict) and e.get("name") == name:
                    out.append(os.path.join(h.skills_cache(stack.name), name, str(e.get("path", "")).strip("/")))
    except (OSError, yaml.YAMLError):
        pass
    return out


def _skill_in(h, stack, name, packs=True):
    for d in _skill_dirs(h, stack, name, packs):
        if os.path.exists(os.path.join(d, "SKILL.md")):
            return os.path.join(d, "SKILL.md")
    return None


def _skill_result(h, stack, name, p, frm):
    over = stack.name not in RESERVED and p.startswith(os.path.join(h.overlay_path, "overrides") + os.sep)
    return {"stack": stack.name, "kind": "skill", "name": name, "path": p, "layer": OVERLAY if over else stack.name,
            "overridden_by": OVERLAY if over else None, "exported": exported(stack, f"my-skills/{name}"),
            "layers": [p], "from": frm}


def resolve_skill(h, ref, frm=None):
    sname, rest = split_ref(ref)
    name = rel_path("skill", rest)
    if sname:
        st = h.get(sname)
        if st is None:
            raise ResolveError(NOT_FOUND, f"no stack {sname!r} installed")
        p = _skill_in(h, st, name)
        if not p:
            raise ResolveError(NOT_FOUND, f"skill {sname}:{name} not found")
        _check_export(st, f"my-skills/{name}", frm)
        return _skill_result(h, st, name, p, frm)
    # bare: framework (reserved), the overlay's my-skills, this stack (my-skills, then its skills.yaml packs), its
    # requires, then any installed stack that exports it. The overlay's packs count only for its own refs (or with no
    # --from), so a stack that pins a skill gets its own copy (ADR 0011, 9.2).
    me = h.get(frm) if frm else None
    own = me is None or me.name == OVERLAY
    levels = [([h.psai], True), ([h.overlay], own)]
    if not own and me.name not in RESERVED:
        levels.append(([me], True))
        req = [h.get(r.get("name")) for r in (me.meta.get("requires") or []) if isinstance(r, dict)]
        levels.append(([s for s in req if s is not None], True))
    levels.append(([s for s in h.stacks if s is not me], True))
    for i, (level, packs) in enumerate(levels):
        hits = []
        for st in level:
            p = _skill_in(h, st, name, packs)
            if p and (i < len(levels) - 1 or exported(st, f"my-skills/{name}") or not frm):
                hits.append((st, p))
        if len(hits) == 1:
            return _skill_result(h, hits[0][0], name, hits[0][1], frm)
        if len(hits) > 1:
            raise ResolveError(AMBIGUOUS, f"skill {name!r} is in several stacks at the same level: "
                                          f"{', '.join(s.name for s, _ in hits)}; qualify it as <stack>:{name}",
                               [f"{s.name}:{name}" for s, _ in hits])
    raise ResolveError(NOT_FOUND, f"skill {name!r} not found")


def resolve_all(kind, ref, frm=None, h=None):
    """Every existing layer of a ref, winner first, as result dicts (layers list in each)."""
    h = h or home()
    if kind is None:
        _, rest = split_ref(ref)
        kind = kind_of(rest)
    if kind == "skill":
        return resolve_skill(h, ref, frm)
    sname, rest = split_ref(ref)
    path = rel_path(kind, rest)
    knowledge = kind == "knowledge"
    if sname:
        st = h.get(sname)
        if st is None:
            raise ResolveError(NOT_FOUND, f"no stack {sname!r} installed")
        cands = [st]
    elif frm:
        st = h.get(frm)
        if st is None:
            raise ResolveError(NOT_FOUND, f"--from {frm}: no such stack")
        cands = [st]
    else:
        cands = h.content_stacks()
    hits = []
    for st in cands:
        layers = _layers(h, st, path, knowledge)
        if any(os.path.exists(p) for _, p in layers):
            hits.append((st, layers))
    if not hits:
        where = cands[0].name if len(cands) == 1 else "any installed stack"
        raise ResolveError(NOT_FOUND, f"{kind} {path} not found in {where}")
    if len(hits) > 1 and hits[0][0].name != OVERLAY:
        raise ResolveError(AMBIGUOUS, f"{path} is in several stacks: {', '.join(s.name for s, _ in hits)}; "
                                      f"qualify it as <stack>:{path}", [f"{s.name}:{path}" for s, _ in hits])
    st, layers = hits[0]
    _check_export(st, path, frm)
    return _result(h, kind, st, path, layers, frm)


def resolve(kind, ref, frm=None, h=None):
    """The absolute path of the winning file. Raises ResolveError (code 3, 4 or 5)."""
    return resolve_all(kind, ref, frm, h)["path"]


def write_target(kind, ref, frm=None, h=None):
    """Where a write for this ref belongs: inboxes and the overlay's own files in the overlay, a pinned stack's file as
    an override in the overlay, a dev stack's file in its clone."""
    h = h or home()
    if kind is None:
        kind = kind_of(split_ref(ref)[1])
    sname, rest = split_ref(ref)
    path = rel_path(kind, rest)
    if kind == "skill":
        path = f"my-skills/{path}/SKILL.md"
    st = h.get(sname or frm or OVERLAY)
    if st is None:
        raise ResolveError(NOT_FOUND, f"no stack {sname or frm!r} installed")
    if st.name == "psai":
        raise ResolveError(NOT_EXPORTED, "the framework's files can't be written or overridden; change psai by PR")
    if st.name == OVERLAY:
        return os.path.join(h.overlay_path, path)
    if kind == "knowledge":
        return os.path.join(h.overlay_path, "knowledge", st.name, path[len("knowledge/"):])
    if st.mode == "dev":
        return os.path.join(st.path, path)
    return os.path.join(h.overlay_path, "overrides", st.name, path)


# ---------- CLI ----------
def main(argv=None):
    ap = argparse.ArgumentParser(prog="psai resolve", description="Find psai content by name (ADR 0011, section 5).")
    ap.add_argument("args", nargs="+", metavar="[kind] ref")
    ap.add_argument("--from", dest="frm", help="the stack whose file holds the ref (what a bare ref means)")
    ap.add_argument("--all", action="store_true", help="print every layer, winner first")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true", help="print where a write for the ref belongs")
    ap.add_argument("--home", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if len(a.args) == 1:
        kind, ref = None, a.args[0]
    elif len(a.args) == 2 and a.args[0] in KINDS:
        kind, ref = a.args
    else:
        ap.error(f"expected [kind] ref; kinds: {' '.join(KINDS)}")
    h = Home(a.home)
    try:
        if a.write:
            p = write_target(kind, ref, a.frm, h)
            print(json.dumps({"path": p}) if a.json else p)
            return 0
        r = resolve_all(kind, ref, a.frm, h)
    except ResolveError as e:
        if a.json:
            print(json.dumps({"error": e.msg, "code": e.code, "candidates": e.candidates}))
        print(f"psai resolve: {e.msg}", file=sys.stderr)
        return e.code
    if a.json:
        print(json.dumps({k: v for k, v in r.items() if k != "from"}, sort_keys=True))
    elif a.all:
        print("\n".join(r["layers"]))
    else:
        print(r["path"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
