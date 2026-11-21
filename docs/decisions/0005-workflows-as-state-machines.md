# 0005: Workflows are state machines; the engine is generic (2026-11-21)
- Decision: a workflow is YAML: nodes with `step`, an optional `role`, `human`, `fan_out` or `skill`, and ordered `next` edges where the first match wins and the last edge is the default. `escalate` returns to the caller, and `ready` is terminal. Added `handoff: <workflow>` as a third kind of end, so one workflow can pass work to another. A size decision is an edge out of clarify, not a separate node, because the spec's step list has no size step. ROUTING.yaml is a decision tree whose leaves are workflows.
- Why: the owner accepted the state-machine format. With an explicit graph, check.sh can validate it, simulate.py can test it and graph.py can draw it.
- Source: the owner's v2 spec.
