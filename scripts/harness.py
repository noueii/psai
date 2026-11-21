"""Shared helpers for check.sh, simulate.py and graph.py: load and validate a harness root.

A harness root holds workflows/, steps/, roles/, guides/, templates/, knowledge/ (vanilla or test content).
"""
import os
import re
import sys

import yaml

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


def validate(root):
    errs = []
    rel = lambda p: os.path.relpath(p, root)
    exists = lambda p: os.path.exists(os.path.join(root, p))

    def check_reads(path):
        fm = frontmatter(path)
        reads = fm.get("read", []) or []
        if not isinstance(reads, list):
            errs.append(f"{rel(path)}: read: must be a list")
            return fm
        for r in reads:
            if not exists(r):
                errs.append(f"{rel(path)}: read: {r} does not exist")
        return fm

    for d in ("steps", "roles"):
        dd = os.path.join(root, d)
        for f in sorted(os.listdir(dd)) if os.path.isdir(dd) else []:
            if f.endswith(".md") and f != "README.md":
                fm = check_reads(os.path.join(dd, f))
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
                if "handoff" in n and not os.path.exists(os.path.join(root, "workflows", f"{n['handoff']}.yaml")):
                    errs.append(f"{where}: {nid}: handoff to missing workflow {n['handoff']!r}")
                continue
            if "step" not in n:
                errs.append(f"{where}: {nid}: missing step")
            elif not exists(n["step"]):
                errs.append(f"{where}: {nid}: step {n['step']} does not exist")
            if n.get("role") and not exists(f"roles/{n['role']}.md"):
                errs.append(f"{where}: {nid}: role {n['role']!r} has no brief roles/{n['role']}.md")
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
    return errs


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
            rx = re.sub(r"<[^>]+>", "[^/]+", p.replace(".", r"\."))
            pats.append(re.compile("^" + rx + "$"))
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
                pats.append(re.compile("^" + re.sub(r"<[^>]+>", "[^/]+", p.replace(".", r"\.")) + "$"))
    return pats


def user_files(root, layout_md, paths):
    """The subset of `paths` (relative to root) that LAYOUT.md gives to the user."""
    pats = owner_patterns(layout_md)
    return [p for p in paths if os.path.basename(p) != "README.md" and any(rx.match(p) for rx in pats)]


def check_layout(root, layout_md, dirs=("workflows", "steps", "roles", "guides", "templates", "knowledge")):
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


def context(root, shown=None):
    """The always-on nudge every harness plugin injects: global.md, owner.md, the routing line, and each workflow's
    name and `when`. Deterministic: same files, same text. The routing logic itself is the request-router skill."""
    shown = shown or root
    parts = [open(os.path.join(root, "instructions", "global.md")).read().strip()]
    owner = os.path.join(root, "instructions", "owner.md")
    if os.path.exists(owner):
        parts.append("## Owner rules\n" + open(owner).read().strip())
    lines = [f"For every request, run the request-router skill first (`{shown}/skills/request-router/SKILL.md`). "
             "Skip it only for a quick question or a one-off reply.", "", "Workflows:"]
    wfs = workflow_files(root)
    for path in wfs:
        wf = load(path) or {}
        lines.append(f"- {wf.get('name', os.path.basename(path)[:-5])}: {' '.join(str(wf.get('when', '')).split())}")
    if not wfs:
        lines.append("- none yet (customize-harness creates the first one)")
    parts.append("\n".join(lines))
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "context":
    # harness.py context [root] [shown-root]: print the injected text
    r = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("HARNESS_HOME") or os.path.expanduser("~/.harness")
    sys.stdout.write(context(r, sys.argv[3] if len(sys.argv) > 3 else None))
    sys.exit(0)

if __name__ == "__main__":
    root = sys.argv[1]
    problems = validate(root) + check_layout(root, sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "LAYOUT.md"))
    for p in problems:
        print("  FAIL", p)
    sys.exit(1 if problems else 0)
