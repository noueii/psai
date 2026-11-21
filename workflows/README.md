# workflows/

The owner's workflows, one state machine per file, plus `ROUTING.yaml`, which picks one for each task. Vanilla ships with no workflows: `work` escalates and offers `customize-harness`. Example: [evals/fixtures/harness-content/workflows/example.yaml](../evals/fixtures/harness-content/workflows/example.yaml). Your diagrams are generated into `GRAPHS.md`.

## `<name>.yaml`
```yaml
name: example
when: Any task that changes files in a repo.     # what the workflow is for
start: do
defaults: { max: 2, on_exhaust: escalate }       # limit for automatic loops back
nodes:
  do:
    step: steps/do.md                            # required, except on special nodes
    role: doer                                   # optional: run by a fresh role agent
    next:                                        # checked in order; first match wins
      - { when: blocked, to: escalate }
      - { to: check }                            # the last edge is the default
  check:
    step: steps/check.md
    role: checker
    next:
      - { when: changes needed, to: do }         # a loop back: limited by defaults.max
      - { when: done, to: ready }
  escalate: { return: caller }                   # special: answer resumes the asker
  ready: { terminal: true }                      # special: the end
```
- **Other node keys:**
  - `human: true`: a human gate; loops it drives have no limit;
  - `fan_out: [lens, ...]`: one role agent per lens;
  - `skill: <name>`: use that skill for the step.
- **Special nodes:** `handoff: <workflow>` continues in another workflow.
- **Edge keys:** `when`, `to`, `max`. An edge back to an earlier node is a loop: if neither it nor its node is human, it must have a limit (its own `max` or `defaults.max`).
- **check.sh enforces:**
  - every node is reachable from `start`;
  - every path can end at a `terminal`, `escalate` or `handoff` node;
  - every `step`, `role` and `read:` path exists.

## `<name>.cases.yaml`
Scripted runs for `scripts/simulate.py`:
```yaml
- name: the check loop is limited
  take: { check: [changes needed, changes needed, changes needed] }   # per node, the edge taken on each visit; unscripted = default
  ends: escalate                          # or ready, or handoff:<wf>
  asker: check                            # optional: which node escalated
  path: [do, check, do, check, do, check, escalate]   # optional: exact path
```

## `ROUTING.yaml`
A decision tree, created with your first workflow; vanilla has none, so every task escalates. Each node is `{ ask, answers: [{ if, then }] }`, `{ workflow: <name> }` or `{ escalate: <reason> }`. No match: escalate. Example: [evals/fixtures/harness-content/workflows/ROUTING.yaml](../evals/fixtures/harness-content/workflows/ROUTING.yaml). Routing cases go in `ROUTING.cases.yaml`: `- { name, answers: [yes, ...], workflow: <name> }` or `escalate: true`.
