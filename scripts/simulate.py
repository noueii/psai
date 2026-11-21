#!/usr/bin/env python3
"""Walk workflows with scripted outcomes and assert the path (L2).

Usage: simulate.py <harness-root> [--verbose]
Runs every workflows/<name>.cases.yaml against workflows/<name>.yaml, and ROUTING.cases.yaml against ROUTING.yaml.
In a case, `take: {node: [when, ...]}` gives the edge taken on each visit; an unscripted visit takes the default
(last) edge. Edge limits follow the engine: an edge's max, or defaults.max for an automatic loop back; one more
trip goes to defaults.on_exhaust.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402

STEP_CAP = 500


def run(wf, take=None):
    take = {k: list(v) for k, v in (take or {}).items()}
    nodes, exhaust = wf["nodes"], (wf.get("defaults") or {}).get("on_exhaust")
    path, counts, cur, asker = [], {}, wf["start"], None
    while len(path) < STEP_CAP:
        path.append(cur)
        n = nodes[cur] or {}
        if n.get("terminal"):
            return path, cur, asker
        if "handoff" in n:
            return path, f"handoff:{n['handoff']}", asker
        if "return" in n:
            return path, cur, asker
        edges = n["next"]
        want = take.get(cur, [])
        if want:
            w = want.pop(0)
            match = [e for e in edges if e.get("when") == w]
            if not match:
                raise ValueError(f"{cur}: no edge with when {w!r}")
            edge = match[0]
        else:
            edge = edges[-1]
        key = (cur, edge["to"], edge.get("when"))
        counts[key] = counts.get(key, 0) + 1
        limit = harness.edge_limit(wf, cur, edge)
        if limit is not None and counts[key] > limit:
            asker = cur
            cur = exhaust
            continue
        if edge["to"] in nodes and "return" in (nodes[edge["to"]] or {}):
            asker = cur
        cur = edge["to"]
    raise RuntimeError("step cap reached (endless loop?)")


def route(tree, answers):
    answers = list(answers)
    while True:
        if "workflow" in tree:
            return ("workflow", tree["workflow"])
        if "escalate" in tree:
            return ("escalate", tree["escalate"])
        if not answers:
            return ("escalate", "no answer")
        a = answers.pop(0)
        match = [x for x in tree.get("answers", []) if str(x.get("if")) == str(a)]
        if not match:
            return ("escalate", f"no branch for {a!r}")
        tree = match[0]["then"]


def main(root, verbose=False):
    fails, total = 0, 0
    wdir = os.path.join(root, "workflows")
    for path in harness.workflow_files(root):
        name = os.path.basename(path)[:-5]
        cpath = os.path.join(wdir, f"{name}.cases.yaml")
        if not os.path.exists(cpath):
            print(f"  FAIL {name}: no {name}.cases.yaml")
            fails += 1
            continue
        wf = harness.load(path)
        for case in harness.load(cpath) or []:
            total += 1
            try:
                p, end, asker = run(wf, case.get("take"))
                ok = True
                if "path" in case and p != case["path"]:
                    ok = False
                if "ends" in case and end != case["ends"]:
                    ok = False
                if "asker" in case and asker != case["asker"]:
                    ok = False
                if not any(k in case for k in ("path", "ends")):
                    ok = False
                msg = " -> ".join(p) + (f" (asker {asker})" if asker else "")
            except (ValueError, RuntimeError, KeyError) as e:
                ok, msg = False, str(e)
            print(f"  {'ok  ' if ok else 'FAIL'} {name}: {case['name']}" + (f"\n         {msg}" if verbose or not ok else ""))
            fails += not ok
    rc = os.path.join(wdir, "ROUTING.cases.yaml")
    if os.path.exists(rc):
        tree = harness.load(os.path.join(wdir, "ROUTING.yaml"))["tree"]
        for case in harness.load(rc) or []:
            total += 1
            kind, val = route(tree, case.get("answers", []))
            ok = (kind == "workflow" and val == case.get("workflow")) or (kind == "escalate" and case.get("escalate"))
            print(f"  {'ok  ' if ok else 'FAIL'} ROUTING: {case['name']}" + ("" if ok else f" (got {kind} {val})"))
            fails += not ok
    print(f"simulate: {total - fails}/{total} cases passed")
    return 1 if fails else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], "--verbose" in sys.argv))
