---
name: customize-harness
description: "Builds and changes the owner's harness setup WITH the owner: bootstraps a first workflow from the vanilla harness by interviewing them, or adds or changes one piece (workflow, routing, step, role, guide, template, owner rule). Use when `work` finds no matching workflow and the owner agrees to set one up, when the owner wants to change how agents work, or when a proposed-rule from an inbox is accepted."
---

# customize-harness

`H` is the harness root (`$HARNESS_HOME` or `~/.harness`). Everything you write is filed per `H/LAYOUT.md`. Changes reach the owner as a branch or PR they merge; never merge yourself. If `H` is the live install, work in a separate worktree (`git -C H worktree add ...`), because live sessions read `H`.

## How to ask
Ask the owner ONE question per message, with the fixed block, kind `question`, node `customize` (`H/skills/work/escalation.md`). Offer options with your recommendation first. Don't ask what the owner already told you or what LAYOUT.md settles.

## Bootstrap (no workflows yet)
1. **Interview** the owner about how they work, one question at a time:
   - what kinds of tasks they hand to agents;
   - the steps a task goes through, and where a human must look;
   - which roles exist and what each may change;
   - which checks prove the work is right;
   - when agents may decide alone and when they must ask;
   - what a finished handover contains.
2. **Offer the design patterns** in [patterns/](patterns/) as options, one at a time and only where they fit. Never add one the owner didn't choose:
   - [separate roles](patterns/separate-roles.md)
   - [a checker that works from the spec](patterns/checker-from-spec.md)
   - [change limits enforced by diff](patterns/diff-limits.md)
   - [loop limits](patterns/loop-limits.md)
   - [sizing](patterns/sizing.md)
   - [a handover template](patterns/handover.md)
   - [a decide-and-log escalation policy](patterns/decide-and-log.md)
3. **Propose** the first workflow as a short summary: nodes, edges, roles, attachments. Ask for acceptance, then build it (below).

## Add or change one piece
1. Ask what should change and why, if that isn't clear yet.
2. Ask the scope: everywhere, this workflow only, or this repo only (`<repo>/.harness/`, same layout, created on first use).
3. Pick the place and format from LAYOUT.md.

## Build
1. Write the files per LAYOUT.md, using the formats in each folder's README.md. For a role, also create `knowledge/roles/<role>/INDEX.md` and `inbox.md`.
2. For a new workflow, also write:
   - its branch in `workflows/ROUTING.yaml`;
   - its simulator cases `workflows/<name>.cases.yaml`, covering every edge you added, every loop limit and every escalation;
   - at least one eval scenario `evals/scenarios/<name>.yaml`.
3. Validate:
   - `H/scripts/check.sh --quick`;
   - `python3 H/scripts/simulate.py H`;
   - `python3 H/scripts/graph.py H --update-readme`.

   Fix until all three pass.
4. Commit on a branch named `customize/<slug>`. Open a PR if the repo has a remote and the owner wants one. Report what you added, where, and how to try it.
