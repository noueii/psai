# Formats

Where each file goes: [LAYOUT.md](LAYOUT.md). A SKILL.md uses only the Agent Skills frontmatter fields (`name`, `description`, `license`, `allowed-tools`, `metadata`, `compatibility`); any other key makes some tools drop the skill. Other files may have any frontmatter.

## Refs
A file named in a workflow, step or role is a **ref**:
- `path`: relative to the folder of the skill holding the file that names it, e.g. `steps/do.md`, `guides/style.md`;
- `skill:path`: the file `path` in the folder of the skill `skill`, e.g. `acme-shared:guides/style.md`.

## Workflow skill: `workflow-<stack>-<name>/SKILL.md`
```md
---
name: workflow-acme-change
description: "Workflow: any task that changes files in a repo. Use when request-router picks it, or the owner asks for it by name."
---

# workflow-acme-change

A psai workflow: run it with the `work` skill. The state machine is [workflow.yaml](workflow.yaml); every file it names is relative to this folder, or `skill:path`.
```
The description starts with `Workflow:` and says what the workflow is for: the router matches requests on it.

## `workflow.yaml`
```yaml
start: do
defaults: { max: 2, on_exhaust: escalate }       # limit for automatic loops back
nodes:
  do:
    step: steps/do.md                            # required, except on special and skill nodes
    role: roles/doer.md                          # optional: run by a fresh role agent (a ref)
    next:                                        # checked in order; first match wins
      - { when: blocked, to: escalate }
      - { to: check }                            # the last edge is the default
  check:
    step: steps/check.md
    role: acme-shared:roles/checker.md
    next:
      - { when: changes needed, to: do }         # a loop back: limited by defaults.max
      - { when: done, to: report }
  report: { step: steps/report.md, next: [{ to: ready }] }
  escalate: { return: caller }                   # special: the answer resumes the asker
  ready: { terminal: true }                      # special: the end
```
- **Other node keys:** `human: true` (a human gate; loops it drives have no limit), `fan_out: [lens, ...]` (one role agent per lens), `skill: <name>` (use that skill for the step, e.g. `retro: { skill: retro, next: [{ to: sync }] }`; needs no `step`).
- **Special nodes:** `terminal: true`, `return: caller`, `handoff: <workflow skill>` (continue in another workflow).
- **Edge keys:** `when`, `to`, `max`. An edge back to an earlier node is a loop: unless it or its node is human, it needs a limit (its own `max` or `defaults.max`).
- **The checks enforce:** every node is reachable from `start`; every path can end at a `terminal`, `return` or `handoff` node; every automatic loop is limited; every ref resolves.
- **Retro and sync:** `work` runs the `retro` skill after every workflow; a `retro` node only fixes its place. `sync` runs only at a `sync` node.

## Step: `steps/<name>.md`
```md
---
read: [guides/style.md, templates/report.md]     # refs read with the step
skills: { optional: [acme-changelog] }           # optional
---
Do X. Done when Y.
```

## Role: `roles/<name>.md`
```md
---
may_change: tests              # anything | tests | nothing: check-diff.sh enforces it
read: [guides/testing.md]      # refs the role reads first
skills: { required: [acme-lint], optional: [] }
model: strong                  # optional: fast | balanced | strong, or {claude: opus, pi: <provider/id>}
---
You are the checker. You work only from the spec ...
```
The role's name is the file's name; its knowledge is `knowledge/roles/<name>/` in your stack.

## Guide: `guides/<name>.md`
Prescriptive prose for one kind of work, attached with `read:`. No frontmatter needed.

## Template: `templates/<name>.md`
The exact output format, then a filled-in example. Attached with `read:`.

## Rules skill: `<stack>-rules/SKILL.md`
```md
---
name: acme-rules
description: "acme's rules for every task: when to escalate, what to log. Use when request-router starts on a request, before choosing a workflow."
---
- Escalate before deleting data or changing a public API.
- Log every decision taken alone in the final report.
```
A few bullets. The router loads every `*-rules` skill; your own stack's win.

## Shared skill: `<stack>-shared/SKILL.md`
```md
---
name: acme-shared
description: "Roles, guides and templates that acme's workflows share. Use when a workflow, step or role names a file in acme-shared."
---
- `roles/checker.md`: checks a change against the spec; may change tests.
- `guides/style.md`: house style for prose.
```

## Simulator cases: `evals/cases/<workflow skill>.yaml`
```yaml
- name: the check loop is limited
  take: { check: [changes needed, changes needed, changes needed] }   # per node, the edge taken on each visit
  ends: escalate                     # the node the run ends at, or handoff:<workflow skill>
  asker: check                       # optional: the node that escalated
  path: [do, check, do, check, do, check, escalate]                   # optional: the exact path
```
An unscripted visit takes the default (last) edge. Cover every edge, every loop limit and every escalation.

## Knowledge (your own stack)
- `knowledge/INDEX.md`: one line per file: `- [title](path): what it holds`.
- `knowledge/inbox.md`, `knowledge/roles/<role>/inbox.md`: dated entries (the `capture-knowledge` skill).
- `knowledge/facts/<topic>.md`: prose with sources. `knowledge/decisions/YYYY-MM-DD-<slug>.md`: Decision / Why / Source.
