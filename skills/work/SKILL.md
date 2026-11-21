---
name: work
description: "The harness engine: runs a chosen workflow node by node with fresh role agents, diff checks, loop limits, escalations and a final report. Use when request-router has matched a request to one of the owner's workflows, before doing any of the work yourself."
---

# work

Every file is found by name through the `psai` command (the nudge says how to run it if it isn't on PATH): never build paths yourself. A workflow is `stack:name`, or a bare name when one stack has it. The workflow file is the source of truth; this skill only says how to run it.

## 1. Route
The `request-router` skill decides which workflow runs (or none). This file is the engine you read once it has. If you got here without routing, run request-router first. Never improvise a workflow.

## 2. Run the workflow
Read the workflow (`psai resolve workflow <workflow>`) and begin at `start`. On entering EVERY node, the first one and `ready` included, first run `psai trace <workflow> <id>`. It records the path and refuses a move that isn't an edge of the workflow, or a move on from a role node whose diff wasn't checked. If it refuses, fix the cause; never work around it. Never skip a node because a task looks small: sizing is already in the workflow's edges. Then run `psai node <workflow> <id>`: it prints the node's files, resolved. Then:
- Read its step and every `read:` file listed under it.
- **`role: <r>`:** delegate (section 4) to a FRESH agent. Give it what `psai node` lists for the role:
  - its brief and the brief's `read:` files;
  - its knowledge files;
  - the step;
  - the spec;
  - the base commit;
  - its skills (the role's and the step's `skills:`, resolved). Exit 3 from `psai node` means a required skill is missing: don't start the role; escalate from this node, offering to install it with `customize-harness`. A missing optional skill goes in the final report; carry on.

  With `fan_out`, start one fresh agent per lens, never merging lenses. Run section 3 after EVERY role agent, fan-out agents included.
- **`human: true`:** ask the human with the fixed block, kind `review` (escalation.md), and wait.
- **`skill: <s>`:** use that skill for the step (`retro`, `sync`, or any other). A skill node may have no `step:`.
- **No `role:`** (e.g. running checks, writing the report): do the step yourself. Never delegate it, and never skip it.

Then choose the edge:
1. Check `next` in order. The first edge whose `when` holds wins; the last edge is the default.
2. **Limits:** an edge's `max` (or `defaults.max` for an automatic edge back to an earlier node) caps how often you take it for the same problem. If taking it again would exceed the cap, go to `defaults.on_exhaust` instead.

Special nodes:
- **`escalate`:** emit the block (kind `escalation`, with the asking node), wait for the answer, then resume the node that asked (`return: caller`).
- **`handoff: <wf>`:** continue in that workflow (as `psai node` names it) at its start, carrying the spec.
- **`terminal`:** run `trace.sh` for it. If this run passed no `retro` node, run the retro skill now (always: it's how the harness learns). Then end with the final report written by the step before it, plus the retro's `## Retro` section, as your final message.

## 3. Role boundaries
1. Before each role, commit pending work so the tree is clean. Record `base=$(git rev-parse HEAD)`.
2. After the role returns, run `psai check-diff <workflow> <id> "$base"`. It reads `may_change` from the role's brief.
3. **On a violation:** run `git reset --hard "$base" && git clean -fd`, then re-run the role with the violation quoted. A second violation: escalate.
4. Otherwise, commit the role's work: `git add -A && git commit -m "<node>: <summary>"`.

## 4. Delegation per tool
Every role agent starts with a FRESH context and runs in the foreground: wait for its result before choosing the edge. Never end your turn while a role agent runs; only human nodes and escalations end a turn before `ready`. Its prompt starts: "You are the <r> inside a running workflow. Do not run request-router or work, and do not start workflows. Do your brief and return. Read <brief path> and follow it." Then come the inputs listed in section 2. A role may still use capture-knowledge and the skills its brief lists.
Pass the role's model from `psai node`'s `model:` line where your tool can; where it can't (or none is set), use the tool's current model and say "model not settable in <tool>" in the final report.
- **Claude Code:** Agent (Task) tool, `subagent_type: general-purpose`, `model` from the line, not in the background.
- **opencode:** `task` tool, `subagent_type: general`.
- **omp:** `task` tool, agent `task`.
- **pi:** no subagents. Spawn `PSAI_ROLE=<r> pi -p --no-session [--model <id>] "<prompt>"` through bash (`PSAI_ROLE` switches its psai nudge to role mode). If that fails, play the role yourself, sequentially: re-read the brief and work only from the spec.

## Never
Never end a turn with a plain question: ask only with the fixed block. Never merge, deploy, push, or post to people unless a step says so and the human approved it; the retro and sync skills' one PR branch to the owner's fork is the exception. Escalate only by the fixed block (`psai route` prints where it is) and the owner rules in your nudge.
