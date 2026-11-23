# A workflow

A workflow is a skill folder, `skills/workflow-<stack>-<name>/`, that holds everything only it uses:

```
skills/workflow-acme-change/
  SKILL.md          name and description; tells the agent to run it with the work skill
  workflow.yaml     the state machine
  GRAPH.md          optional diagram (customize-harness's graph.py)
  steps/            one file per step
  roles/            roles only this workflow uses
  guides/, templates/
```

## SKILL.md
```md
---
name: workflow-acme-change
description: "Workflow: any task that changes files in a repo. Use when request-router picks it, or the owner asks for it by name."
---

# workflow-acme-change

A psai workflow: run it with the `work` skill. The state machine is [workflow.yaml](workflow.yaml); every file it names is relative to this folder, or `skill:path`.
```
The description starts with `Workflow:` and says what kind of request it is for. `request-router` lists every skill named `workflow-*` and matches the request against these descriptions, so write the description for that match. Only the Agent Skills fields (`name`, `description`, `license`, `allowed-tools`, `metadata`, `compatibility`) may appear in SKILL.md frontmatter.

## workflow.yaml
```yaml
start: do
defaults: { max: 2, on_exhaust: escalate }
nodes:
  do:
    step: steps/do.md
    role: roles/maker.md
    next:
      - { when: blocked, to: escalate }
      - { to: check }
  check:
    step: steps/check.md
    role: acme-shared:roles/tester.md
    next:
      - { when: tests fail, to: do }
      - { when: done, to: approve }
  approve:
    step: steps/approve.md
    human: true
    next:
      - { when: changes requested, to: do }
      - { when: approved, to: report }
  report: { step: steps/report.md, next: [{ to: ready }] }
  escalate: { return: caller }
  ready: { terminal: true }
```

| Node key | Meaning |
|---|---|
| `step: <ref>` | what happens here (required except on special and skill nodes) |
| `role: <ref>` | a fresh role agent does the step; its diff is checked against the role's `may_change` |
| `human: true` | a human gate: the agent asks with the fixed block, kind `review`; loops it drives have no limit |
| `fan_out: [lens, ...]` | one role agent per lens |
| `skill: <name>` | use that skill for the step (`retro`, `sync`, or any other) |
| `next: [...]` | edges, checked in order; the first whose `when` holds wins; the last is the default |
| `terminal: true` | the end: `work` writes the final report and runs the retro |
| `return: caller` | the escalation node: the answer resumes the node that asked |
| `handoff: <workflow skill>` | continue in another workflow |

**Edges** have `when`, `to` and optional `max`. An edge to an earlier node is a loop. Unless it or its node is human, it needs a limit: its own `max`, or `defaults.max`. Past the limit, `work` goes to `defaults.on_exhaust`.

**What the checks enforce:**
- every node is reachable from `start`;
- every path can end (`terminal`, `return` or `handoff`);
- every automatic loop has a limit;
- every ref resolves;
- every simulator case passes.

**At run time,** `work/trace.sh` refuses a move that isn't an edge. It also refuses to move on from a role node before `check-diff.sh` has run for it.

## Refs
A file is named as `path`, relative to the folder of the skill that holds the naming file (`steps/do.md`), or as `skill:path` in another skill's folder (`acme-shared:roles/tester.md`).
