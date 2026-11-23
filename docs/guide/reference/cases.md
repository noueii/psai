# Simulator cases and eval scenarios

Both live outside `skills/`, so they never ship.

## Simulator cases: `evals/cases/<workflow skill>.yaml`
Scripted runs of a workflow, checked by `scripts/check.sh` (and CI) without any model:
```yaml
- name: straight through
  path: [do, check, approve, report, ready]
- name: the test loop is limited
  take: { check: [tests fail, tests fail, tests fail] }   # per node: the edge taken on each visit
  path: [do, check, do, check, do, check, escalate]
  asker: check
```
- `take`: per node, the `when` of the edge taken on each visit. An unscripted visit takes the default (last) edge.
- `path` (the exact path), `ends` (the last node, or `handoff:<workflow skill>`), `asker` (the node that escalated): give `path` or `ends`.

Cover every edge, every loop limit and every escalation.

## Eval scenarios: `evals/scenarios/<name>.yaml`
An AI eval: a task, a fake owner's scripted answers, and what to expect. psai's `evals/run.sh --stack <repo>` runs a stack's scenarios headless in Claude Code with the stack loaded. The format is psai's [evals/scenarios/README.md](../../../evals/scenarios/README.md). Running them is optional and manual-only: they use a real model, cost money, and never run in CI. The simulator cases above are what CI checks.
