#!/usr/bin/env bash
# Usage: trace.sh <workflow folder> <node>     (run from the task's repo on entering every node)
# Records the node in the trace file ($PSAI_TRACE, or <git-dir>/psai-trace; check-diff.sh writes there too) and
# refuses (exit 1, with the reason) a move that isn't an edge of the workflow (nor on_exhaust, nor back to the node
# that escalated, nor a new run at `start`), or a move on from a role node whose diff check-diff.sh hasn't checked.
# Needs python3 with PyYAML; without it, it records the node and says the move wasn't checked.
set -euo pipefail
dir="${1:?workflow folder required}"; node="${2:?node id required}"
file="$dir/workflow.yaml"; [ -f "$file" ] || { echo "trace.sh: no $file" >&2; exit 2; }
wf="$(basename "$(cd "$dir" && pwd -P)")"
trace="${PSAI_TRACE:-$(git rev-parse --absolute-git-dir 2>/dev/null || pwd)/psai-trace}"
touch "$trace"
if ! python3 -c 'import yaml' 2>/dev/null; then
  grep -q "^workflow $wf$" "$trace" || echo "workflow $wf" >> "$trace"
  echo "node $node" >> "$trace"; echo "[harness] node: $node (move not checked: needs python3 with PyYAML)"; exit 0
fi
python3 - "$file" "$wf" "$node" "$trace" <<'PY'
import sys, yaml
path, name, node, trace = sys.argv[1:]
wf = yaml.safe_load(open(path)); nodes = wf["nodes"]
if node not in nodes:
    sys.exit(f"trace.sh: {node!r} is not a node of {name}")
lines = open(trace).read().splitlines()
i = max([k for k, l in enumerate(lines) if l.startswith("workflow ")], default=-1)
run, cur = (lines[i + 1:], lines[i].split()[1]) if i >= 0 else ([], None)
seen = [l.split()[1] for l in run if l.startswith("node ")]
prev = seen[-1] if seen and cur == name else None
if prev:
    p = nodes.get(prev) or {}
    role = p.get("role")
    if role:
        role = role.split(":")[-1].rsplit("/", 1)[-1].removesuffix(".md")
        last = max(k for k, l in enumerate(run) if l == f"node {prev}")
        if not any(l.startswith(f"check-diff role={role} ") for l in run[last + 1:]):
            sys.exit(f"trace.sh: run check-diff.sh for the {role} (node {prev}) before moving on")
    if p.get("terminal"):
        allowed = {wf["start"]}
    elif "return" in p:
        callers = [v for v in seen[:-1] if v != prev]
        allowed = {callers[-1] if callers else wf["start"]}
    else:
        allowed = {e["to"] for e in p.get("next") or []}
        if (wf.get("defaults") or {}).get("on_exhaust"):
            allowed.add(wf["defaults"]["on_exhaust"])
    if node not in allowed:
        sys.exit(f"trace.sh: {prev} -> {node} is not an edge of {name}; allowed: {', '.join(sorted(allowed))}. "
                 "Follow the workflow; never skip a node.")
if not prev or (node == wf["start"] and (nodes.get(prev) or {}).get("terminal")):
    if node != wf["start"]:
        sys.exit(f"trace.sh: a run of {name} starts at {wf['start']!r}, not {node!r}")
    open(trace, "a").write(f"workflow {name}\n")
open(trace, "a").write(f"node {node}\n")
print(f"[harness] node: {node}")
PY
