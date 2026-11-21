"""Shared helpers for check.sh, simulate.py and graph.py: load and validate a harness root.

A harness root holds workflows/, steps/, roles/, guides/, templates/, knowledge/ (vanilla or test content).
"""
import os
import re
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve as res  # noqa: E402
import skills as skillreg  # noqa: E402

SPECIAL = ("terminal", "return", "handoff")
MAY_CHANGE = ("anything", "tests", "nothing")


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)


def frontmatter(path):
    text = open(path).read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return (yaml.safe_load(m.group(1)) or {}) if m else {}


def workflow_files(root):
    d = os.path.join(root, "workflows")
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, f) for f in os.listdir(d)
        if f.endswith(".yaml") and not f.endswith(".cases.yaml") and not f.startswith("ROUTING")
    )


def is_special(node):
    return any(k in node for k in SPECIAL)


def ends(node):
    return node.get("terminal") or "return" in node or "handoff" in node


def back_edges(wf):
    """Edges to a node at or before the source in file order (loops), excluding escalate."""
    order = {nid: i for i, nid in enumerate(wf["nodes"])}
    out = []
    for nid, n in wf["nodes"].items():
        for e in n.get("next", []) or []:
            to = e.get("to")
            tn = wf["nodes"].get(to, {})
            if to in order and order[to] <= order[nid] and "return" not in tn:
                out.append((nid, e))
    return out


def edge_limit(wf, nid, edge):
    """The cap on an edge, or None. Automatic loops back get defaults.max; human-driven ones get none."""
    if edge.get("max") is not None:
        return edge["max"]
    node = wf["nodes"][nid]
    if node.get("human"):
        return None
    if any(e is edge for _, e in back_edges(wf) if _ == nid):
        return (wf.get("defaults") or {}).get("max")
    return None


def routing_leaves(tree, out=None):
    out = [] if out is None else out
    if not isinstance(tree, dict):
        return out
    if "workflow" in tree:
        out.append(tree["workflow"])
    for a in tree.get("answers", []) or []:
        routing_leaves(a.get("then"), out)
    return out


def stack_root(arg):
    """A stack given as a path (a folder) or as an installed stack's name, as a folder."""
    if os.path.isdir(arg):
        return arg
    st = res.home().get(arg)
    if st is None:
        raise SystemExit(f"no stack or folder {arg!r}")
    return st.path


def stack_name(root):
    return res.load_stack(root).get("name") or res.OVERLAY


def ref_error(root, kind, ref, h=None):
    """None if `ref` (as written in a file of the stack at `root`) resolves, else why not. A ref to the stack's own
    files is checked in `root`; a `stack:` ref to another stack goes through psai resolve, exports included."""
    name = stack_name(root)
    sname, rest = res.split_ref(ref)
    if sname is None or sname == name:
        if kind == "skill":
            return None
        p = res.rel_path(kind, rest)
        return None if os.path.exists(os.path.join(root, p)) else f"{p} does not exist"
    try:
        res.resolve(kind, ref, frm=name, h=h or res.home())
        return None
    except res.ResolveError as e:
        return e.msg


def validate(root, h=None):
    """Errors in one stack's content (a harness root). Refs to other stacks resolve through the home `h`
    ($PSAI_HOME by default)."""
    errs = []
    rel = lambda p: os.path.relpath(p, root)
    exists = lambda p: os.path.exists(os.path.join(root, p))
    bad = lambda kind, ref: ref_error(root, kind, ref, h)

    def check_reads(path):
        fm = frontmatter(path)
        reads = fm.get("read", []) or []
        if not isinstance(reads, list):
            errs.append(f"{rel(path)}: read: must be a list")
            return fm
        for r in reads:
            why = bad("file", r)
            if why:
                errs.append(f"{rel(path)}: read: {r}: {why}")
        return fm

    for d in ("steps", "roles"):
        dd = os.path.join(root, d)
        for f in sorted(os.listdir(dd)) if os.path.isdir(dd) else []:
            if f.endswith(".md") and f != "README.md":
                fm = check_reads(os.path.join(dd, f))
                errs += [f"{d}/{f}: {e}" for e in skillreg.role_skills(os.path.join(dd, f))[2]]
                if d == "roles" and "model" in fm:
                    import models  # noqa: PLC0415
                    errs += [f"roles/{f}: {e}" for e in models.validate(fm["model"])]
                if d == "roles" and fm.get("may_change") not in MAY_CHANGE:
                    errs.append(f"roles/{f}: may_change must be one of {', '.join(MAY_CHANGE)}")
                if d == "roles" and not exists(f"knowledge/roles/{f[:-3]}/INDEX.md"):
                    errs.append(f"roles/{f}: missing knowledge/roles/{f[:-3]}/INDEX.md")

    names = []
    for path in workflow_files(root):
        try:
            wf = load(path)
        except yaml.YAMLError as e:
            errs.append(f"{rel(path)}: {e}")
            continue
        stem = os.path.basename(path)[:-5]
        names.append(stem)
        where = rel(path)
        for k in ("name", "when", "start", "nodes"):
            if k not in (wf or {}):
                errs.append(f"{where}: missing {k}")
        if not wf or "nodes" not in wf:
            continue
        if wf.get("name") != stem:
            errs.append(f"{where}: name {wf.get('name')!r} != file name {stem!r}")
        nodes = wf["nodes"]
        if wf.get("start") not in nodes:
            errs.append(f"{where}: start {wf.get('start')!r} is not a node")
        exh = (wf.get("defaults") or {}).get("on_exhaust")
        if exh and exh not in nodes:
            errs.append(f"{where}: defaults.on_exhaust {exh!r} is not a node")
        for nid, n in nodes.items():
            n = n or {}
            if is_special(n):
                if "handoff" in n and bad("workflow", str(n["handoff"])):
                    errs.append(f"{where}: {nid}: handoff to missing workflow {n['handoff']!r}: "
                                f"{bad('workflow', str(n['handoff']))}")
                continue
            if "step" not in n:
                if not n.get("skill"):  # a skill node (e.g. retro, sync) may stand without a step
                    errs.append(f"{where}: {nid}: missing step")
            elif bad("file", n["step"]):
                errs.append(f"{where}: {nid}: step {n['step']}: {bad('file', n['step'])}")
            if n.get("role") and bad("role", str(n["role"])):
                errs.append(f"{where}: {nid}: role {n['role']!r} has no brief: {bad('role', str(n['role']))}")
            if n.get("skill") and not exists(f"skills/{n['skill']}/SKILL.md") and not os.path.exists(
                    os.path.join(os.path.dirname(__file__), "..", "skills", n["skill"], "SKILL.md")):
                errs.append(f"{where}: {nid}: skill {n['skill']!r} not found")
            if not n.get("next"):
                errs.append(f"{where}: {nid}: no next edges and not a special node")
            for e in n.get("next", []) or []:
                if e.get("to") not in nodes:
                    errs.append(f"{where}: {nid}: edge to unknown node {e.get('to')!r}")
        # reachable from start
        seen, todo = set(), [wf.get("start")]
        while todo:
            x = todo.pop()
            if x in seen or x not in nodes:
                continue
            seen.add(x)
            todo += [e.get("to") for e in (nodes[x] or {}).get("next", []) or []]
            if exh and not is_special(nodes[x] or {}):
                todo.append(exh)
        for nid in nodes:
            if nid not in seen:
                errs.append(f"{where}: {nid}: not reachable from start")
        # every node can reach an end
        good = {nid for nid, n in nodes.items() if ends(n or {})}
        changed = True
        while changed:
            changed = False
            for nid, n in nodes.items():
                if nid not in good and any(e.get("to") in good for e in (n or {}).get("next", []) or []):
                    good.add(nid)
                    changed = True
        for nid in nodes:
            if nid not in good:
                errs.append(f"{where}: {nid}: no path to ready, escalate or a handoff")
        # automatic loops need a limit
        for nid, e in back_edges(wf):
            if edge_limit(wf, nid, e) is None and not (nodes[nid] or {}).get("human"):
                errs.append(f"{where}: {nid} -> {e.get('to')}: automatic loop without max (and no defaults.max)")
            if edge_limit(wf, nid, e) is not None and not exh:
                errs.append(f"{where}: {nid} -> {e.get('to')}: has a limit but no defaults.on_exhaust")

    rpath = os.path.join(root, "workflows", "ROUTING.yaml")
    if not os.path.exists(rpath):
        if names:
            errs.append("workflows/ROUTING.yaml missing, but there are workflows")
    else:
        r = load(rpath) or {}
        if "tree" not in r:
            errs.append("workflows/ROUTING.yaml: missing tree")
        leaves = routing_leaves(r.get("tree"))
        for leaf in leaves:
            if leaf not in names:
                errs.append(f"workflows/ROUTING.yaml: routes to missing workflow {leaf!r}")
        for n in names:
            if n not in leaves:
                errs.append(f"workflows/{n}.yaml: not reachable from ROUTING.yaml")
    return errs + skillreg.validate_config(root)


def _path_rx(p):
    """A LAYOUT.md path as a regex: <x> matches one segment, a trailing /** anything below."""
    return re.compile("^" + re.sub(r"<[^>]+>", "[^/]+", p.replace(".", r"\.")).replace("/**", "/.+") + "$")


def layout_patterns(layout_md):
    """Regexes from the 'Goes in' column of LAYOUT.md (backticked paths; <x> matches one segment)."""
    pats = []
    for line in open(layout_md):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] in ("You're adding", "---"):
            continue
        for p in re.findall(r"`([^`]+)`", cells[1]):
            if p.startswith("<repo>"):
                continue
            pats.append(_path_rx(p))
    return pats


def owner_patterns(layout_md, owner="you"):
    """Regexes for the paths LAYOUT.md gives to `owner` (you = the fork's user, upstream = psai)."""
    pats = []
    for line in open(layout_md):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[3] != owner:
            continue
        for p in re.findall(r"`([^`]+)`", cells[1]):
            if not p.startswith("<repo>"):
                pats.append(_path_rx(p))
    return pats


# The paths the fork model (before ADR 0011) gave the user, for a fork whose LAYOUT.md has no owner column: migration
# 0002 moves exactly these into the overlay.
LEGACY_USER = ["workflows/<name>.yaml", "workflows/<name>.cases.yaml", "workflows/ROUTING.yaml", "workflows/GRAPHS.md",
               "steps/<name>.md", "roles/<name>.md", "my-skills/<name>/SKILL.md", "my-skills/<name>/**", "skills.yaml",
               "knowledge/roles/<role>/INDEX.md", "knowledge/roles/<role>/inbox.md", "guides/<name>.md",
               "templates/<name>.md", "instructions/owner.md", "knowledge/inbox.md", "knowledge/facts/<topic>.md",
               "knowledge/decisions/<date>-<slug>.md", "knowledge/INDEX.md", "evals/scenarios/<name>.yaml"]


def user_files(root, layout_md, paths):
    """The subset of `paths` (relative to root) that a fork's LAYOUT.md gives to the user (its owner column; the
    legacy list when it has none)."""
    pats = owner_patterns(layout_md) if os.path.exists(layout_md) else []
    pats = pats or [_path_rx(p) for p in LEGACY_USER]
    return [p for p in paths if os.path.basename(p) != "README.md" and any(rx.match(p) for rx in pats)]


def check_layout(root, layout_md, dirs=("workflows", "steps", "roles", "guides", "templates", "knowledge", "my-skills")):
    pats = layout_patterns(layout_md)
    errs = []
    for d in dirs:
        for dp, _, fs in os.walk(os.path.join(root, d)):
            for f in fs:
                p = os.path.relpath(os.path.join(dp, f), root)
                if f == "README.md" or any(rx.match(p) for rx in pats):
                    continue
                errs.append(f"{p}: not a place LAYOUT.md allows")
    return errs


def psai_cmd(root, shown=None):
    """How an agent runs the psai command, as shown in the nudge: the framework's psai.py, through `shown` (the home as
    the plugins print it, e.g. ~/.psai) when the framework sits under the home."""
    h = res.home(root)
    fw, real = os.path.realpath(h.framework), os.path.realpath(root)
    if shown and not h.compat:
        path = f"{shown.rstrip('/')}/framework"
    elif shown and fw == real:
        path = shown
    elif shown and fw.startswith(real + os.sep):
        path = f"{shown.rstrip('/')}/{os.path.relpath(fw, real)}"
    else:
        path = fw
    return f"python3 {path.rstrip('/')}/scripts/psai.py"


def context(root, shown=None):
    """The always-on nudge every harness plugin injects: global.md, owner.md, the routing line, and each workflow's
    name and `when`. Deterministic: same files, same text. The routing logic itself is the request-router skill."""
    shown = shown or root
    parts = [open(os.path.join(res.home(root).framework, "instructions", "global.md")).read().strip()]
    owner = os.path.join(res.home(root).overlay_path, "instructions", "owner.md")
    if os.path.exists(owner):
        parts.append("## Owner rules\n" + open(owner).read().strip())
    lines = ["For every request, run the request-router skill first. Skip it only for a quick question or a "
             f"one-off reply. Run `psai` as `{psai_cmd(root, shown)}` if it isn't on PATH.", "", "Workflows:"]
    import index  # noqa: PLC0415
    wfs, rules, collapsed = index.nudge_lines(index.load(res.home(root)))  # the merged index, within its word budget
    lines += wfs
    if collapsed:
        lines.append("Some stacks are collapsed to one line: run `psai route` for the full list.")
    if rules:
        parts += rules
    if not wfs:
        lines.append("- none yet (customize-harness creates the first one)")
    lines += ["", "To add or change a skill, use customize-harness.",
              "When a task outside a workflow is done and you captured knowledge or staged a change, run the retro skill."]
    try:
        import ledger  # noqa: PLC0415
        pend = len(ledger.pending_retro(root))
    except Exception:  # noqa: BLE001 - the nudge must never fail on the local state
        pend = 0
    if pend:
        lines.append(f"{pend} earlier session(s) ended without a retro: run the retro skill once for them "
                     f"(`psai retro gather`, then finish with --pending).")
    try:
        n = sum(1 for s in skillreg.registry(root).values() if s["unmanaged"])
    except Exception:  # noqa: BLE001 - the nudge must never fail on a broken skills.yaml
        n = 0
    if n:
        lines.append(f"{n} skill(s) in your tool folders aren't managed by psai (`psai skills --unmanaged`); "
                     "customize-harness can adopt them.")
    parts.append("\n".join(lines))
    return "\n\n".join(parts) + "\n"


def role_context(root, shown=None, role=None):
    """The nudge for a role agent (or any subagent) inside a running workflow: the same rules, but no routing, so a
    role never starts a workflow of its own."""
    shown = shown or root
    parts = [open(os.path.join(res.home(root).framework, "instructions", "global.md")).read().strip()]
    owner = os.path.join(res.home(root).overlay_path, "instructions", "owner.md")
    if os.path.exists(owner):
        parts.append("## Owner rules\n" + open(owner).read().strip())
    who = f"the {role} inside a running psai workflow" if role else \
        "a subagent: a role inside a running psai workflow, or a helper another agent started"
    parts.append(f"## Role mode\nYou are {who}. Do not run request-router or work, and do "
                 "not start workflows. Do your brief and return. You may still use the capture-knowledge skill and "
                 f"the skills your brief lists. Run `psai` as `{psai_cmd(root, shown)}` if it isn't on PATH.")
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "skills":
    # harness.py skills [list|check|brief|packs|adopt] ...: the live skill registry (scripts/skills.py)
    sys.exit(skillreg.main(sys.argv[2:]))

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] in ("context", "role-context"):
    # harness.py context|role-context [root] [shown-root]: print the injected text. With $PSAI_ROLE set (work sets
    # it for the role agents it spawns), or as role-context (a plugin detected a subagent), it is the role-mode text.
    r = sys.argv[2] if len(sys.argv) > 2 else res.default_root()
    shown = sys.argv[3] if len(sys.argv) > 3 else None
    role = os.environ.get("PSAI_ROLE", "").strip()
    if role or sys.argv[1] == "role-context":
        sys.stdout.write(role_context(r, shown, role or None))
    else:
        sys.stdout.write(context(r, shown))
    sys.exit(0)

if __name__ == "__main__":
    root = sys.argv[1]
    problems = validate(root) + check_layout(root, sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "LAYOUT.md"))
    for p in problems:
        print("  FAIL", p)
    sys.exit(1 if problems else 0)
