#!/usr/bin/env python3
"""Optional helper: draw a workflow as a Mermaid flowchart. Needs python3 with PyYAML.

Usage: graph.py <workflow folder> [--write]
Prints the diagram; --write puts it in <folder>/GRAPH.md. Each node shows its role and what the role may change.
Loops back are dotted, with their limit.
"""
import os
import re
import sys

import yaml


def role_line(folder, ref):
    path = ref.split(":", 1)[-1]
    name = os.path.splitext(os.path.basename(path))[0]
    p = os.path.join(folder, path) if ":" not in ref else None
    may = None
    if p and os.path.isfile(p):
        m = re.match(r"^---\n(.*?)\n---", open(p).read(), re.S)
        may = (yaml.safe_load(m.group(1)) or {}).get("may_change") if m else None
    return name + (f" · may change: {may}" if may else "")


def mermaid(folder):
    wf = yaml.safe_load(open(os.path.join(folder, "workflow.yaml")))
    nodes, order = wf["nodes"], list(wf["nodes"])
    rank = {n: i for i, n in enumerate(order)}
    q = lambda t: '"' + str(t).replace('"', "'") + '"'
    out = ["flowchart TD", f"  START(({q('task')})) --> {wf['start']}"]
    for nid in order:
        n = nodes[nid] or {}
        if n.get("terminal"):
            out.append(f"  {nid}((({q(nid.upper())})))")
        elif "return" in n:
            out.append(f"  {nid}{{{{{q('ESCALATE to the human')}}}}}")
        elif "handoff" in n:
            out.append(f"  {nid}[/{q('handoff: ' + n['handoff'])}\\]")
        else:
            text = ("human: " if n.get("human") else "") + nid
            if n.get("role"):
                text += f"<br/><i>{role_line(folder, n['role'])}</i>"
            if n.get("fan_out"):
                text += "<br/>lenses: " + ", ".join(n["fan_out"])
            if n.get("skill"):
                text += f"<br/>skill: {n['skill']}"
            a, b = ("[/", "/]") if n.get("human") else ("[", "]")
            out.append(f"  {nid}{a}{q(text)}{b}")
    limit = (wf.get("defaults") or {}).get("max")
    for nid in order:
        for e in (nodes[nid] or {}).get("next") or []:
            back = rank.get(e["to"], 0) <= rank[nid]
            lab = e.get("when", "")
            m = e.get("max", None if (nodes[nid] or {}).get("human") else limit)
            if back and m is not None:
                lab = f"{lab} (max {m})".strip()
            arrow = "-.->" if back else "-->"
            out.append(f"  {nid} {arrow}|{q(lab)}| {e['to']}" if lab else f"  {nid} {arrow} {e['to']}")
    return "\n".join(out)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    text = mermaid(args[0])
    if "--write" in sys.argv:
        name = os.path.basename(os.path.realpath(args[0]))
        with open(os.path.join(args[0], "GRAPH.md"), "w") as f:
            f.write(f"# {name}\n\nDrawn from workflow.yaml by customize-harness's graph.py. Dotted edges loop back.\n\n"
                    f"```mermaid\n{text}\n```\n")
    else:
        print(text)
