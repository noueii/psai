#!/usr/bin/env bash
# Usage: trace.sh <workflow> <node>   (or `psai trace <workflow> <node>`; the workflow is stack:name or a bare name)
# Run on entering every workflow node. It records the node, and refuses (exit 1, with the reason) when:
# - the move doesn't follow the workflow (not an edge from the previous node, nor on_exhaust, nor back to the
#   node that escalated, nor a new run at `start`);
# - the previous node had a role and check-diff.sh hasn't run for it since.
# It also adds the workflow run and each escalation to the session ledger.
# The trace file is $PSAI_TRACE, or <git-dir>/psai-trace. check-diff.sh writes to the same file.
set -euo pipefail
wf="${1:?workflow name required}"
node="${2:?node id required}"
FW="$(cd -P "$(dirname "$0")" && pwd)/../.."   # the framework: this file is skills/work/trace.sh in it
top="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
trace="${PSAI_TRACE:-$(git rev-parse --absolute-git-dir 2>/dev/null || echo "$top")/psai-trace}"
# the workflow's file, and its name as stack:name (bare in a single-root home), so every call names a run the same way
IFS=$'\t' read -r file wf < <(python3 - "$FW/scripts" "$wf" <<'PY'
import sys; sys.path.insert(0, sys.argv[1]); import resolve as r
try:
    x, h = r.resolve_all("workflow", sys.argv[2]), r.home()
except r.ResolveError:
    sys.exit(2)
name = r.rel_path("workflow", r.split_ref(sys.argv[2])[1])[len("workflows/"):-len(".yaml")]
print(x["path"], name if h.compat else f"{x['stack']}:{name}", sep="\t")
PY
) || true
[ -n "${file:-}" ] && [ -f "$file" ] || { echo "trace.sh: no workflow ${1}" >&2; exit 2; }
touch "$trace"
python3 - "$file" "$wf" "$node" "$trace" "$FW" <<'EOF'
import sys, yaml
path, wf_name, node, trace, fw = sys.argv[1:]
def ledger(*args):  # the session ledger (scripts/ledger.py): best-effort
    import os, subprocess
    if os.path.exists(f"{fw}/scripts/ledger.py"):
        subprocess.run([sys.executable, f"{fw}/scripts/ledger.py", *args], capture_output=True)
wf = yaml.safe_load(open(path))
nodes = wf["nodes"]
if node not in nodes:
    sys.exit(f"trace.sh: {node!r} is not a node of {wf_name}")
lines = open(trace).read().splitlines()
# the current run: lines since the last "workflow" marker
start_i = max([i for i, l in enumerate(lines) if l.startswith("workflow ")], default=-1)
run = lines[start_i + 1:] if start_i >= 0 else []
cur_wf = lines[start_i].split()[1] if start_i >= 0 else None
visited = [l.split()[1] for l in run if l.startswith("node ")]
prev = visited[-1] if visited else None
prev_node = (nodes.get(prev) or {}) if cur_wf == wf_name else {}
if cur_wf == wf_name and prev:
    # did check-diff run for the previous role node, after it was entered?
    role = prev_node.get("role")
    if role:
        last = max(i for i, l in enumerate(run) if l == f"node {prev}")
        if not any(l.startswith(f"check-diff role={role} ") for l in run[last + 1:]):
            sys.exit(f"trace.sh: run check-diff.sh for the {role} (node {prev}) before moving on")
    if node == wf["start"] and prev_node.get("terminal"):
        allowed = {node}  # a new task
    elif "return" in prev_node:
        callers = [v for v in visited[:-1] if v != prev]
        allowed = {callers[-1]} if callers else {wf["start"]}
    else:
        allowed = {e["to"] for e in prev_node.get("next", []) or []}
        if (wf.get("defaults") or {}).get("on_exhaust"):
            allowed.add(wf["defaults"]["on_exhaust"])
        if prev_node.get("terminal"):
            allowed = {wf["start"]}
    if node not in allowed:
        sys.exit(f"trace.sh: {prev} -> {node} is not an edge of {wf_name}; allowed: {', '.join(sorted(allowed))}. "
                 f"Follow the workflow; never skip a node.")
else:
    if node != wf["start"]:
        sys.exit(f"trace.sh: a run of {wf_name} starts at {wf['start']!r}, not {node!r}")
    with open(trace, "a") as f:
        f.write(f"workflow {wf_name}\n")
    ledger("workflow", wf_name)
with open(trace, "a") as f:
    f.write(f"node {node}\n")
if "return" in (nodes[node] or {}):
    ledger("escalation")
print(f"[harness] node: {node}")
EOF
