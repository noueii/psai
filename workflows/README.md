# workflows/

The owner's workflows, one state machine per file, plus `ROUTING.yaml`, which picks one for each task. Vanilla ships with no workflows: `work` escalates and offers `customize-harness`. Example: [evals/fixtures/harness-content/workflows/coding.yaml](../evals/fixtures/harness-content/workflows/coding.yaml).

## `<name>.yaml`
```yaml
name: coding
when: A task that changes code, docs or config.   # what the workflow is for
start: clarify
defaults: { max: 2, on_exhaust: escalate }       # limit for automatic loops back
nodes:
  clarify:
    step: steps/clarify.md                       # required, except on special nodes
    next:                                        # checked in order; first match wins
      - { when: blocking question, to: escalate }
      - { to: implement }                        # the last edge is the default
  implement:
    step: steps/implement.md
    role: engineer                               # optional: run by a fresh role agent
    next: [{ to: ready }]
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
- name: verify fails 3x escalates
  take: { verify: [fail, fail, fail] }   # per node, the edge `when` taken on each visit; unscripted = default
  ends: escalate                          # or ready, or handoff:<wf>
  asker: verify                           # optional: which node escalated
  path: [clarify, implement, verify, implement, verify, implement, verify, escalate]   # optional: exact path
```

## `ROUTING.yaml`
A decision tree. Each node is `{ ask, answers: [{ if, then }] }`, `{ workflow: <name> }` or `{ escalate: <reason> }`. No match: escalate. Example: [evals/fixtures/harness-content/workflows/ROUTING.yaml](../evals/fixtures/harness-content/workflows/ROUTING.yaml). Routing cases go in `ROUTING.cases.yaml`: `- { name, answers: [yes, ...], workflow: <name> }` or `escalate: true`.
