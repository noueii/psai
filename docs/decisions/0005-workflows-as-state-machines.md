# 0005: Workflows are state machines; the engine is generic (2026-11-21)
- Decision: a workflow is YAML:
  - nodes with `step`, and optionally `role`, `human`, `fan_out` or `skill`;
  - ordered `next` edges, where the first match wins and the last edge is the default;
  - `escalate` returns to the caller, `ready` is terminal, and `handoff: <workflow>` passes the work to another workflow.

  ROUTING.yaml is a decision tree whose leaves are workflows. `trace.sh` enforces the graph at run time: it refuses non-edges, and refuses to leave a role node until its diff has been checked.
- Why: with an explicit graph, check.sh can validate it, simulate.py can test it, graph.py can draw it and trace.sh can enforce it. Early evals showed agents skipping nodes when only prose told them not to.
- Source: v2 design; evals on 2026-11-21.
