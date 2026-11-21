---
name: work
description: "The harness engine: routes any task through workflows/ROUTING.yaml, then runs the chosen workflow node by node with fresh role agents, diff checks, loop limits, escalations and a handover. Use for every task you are given, before doing the work yourself."
---

# work

`H` is the harness root: `$HARNESS_HOME` if set, else `~/.harness`. A repo may override any file with the same path under `<repo>/.harness/`; the repo's copy wins. The workflow file is the source of truth; this skill only says how to run it.

## 1. Route
1. Read `H/workflows/ROUTING.yaml` and walk its `tree`. At each `ask`, pick the answer (`if`) that fits the task, then follow its `then`.
2. A `workflow:` leaf names the workflow to run.
3. If you reach an `escalate:` leaf, no answer fits, or you're unsure, escalate (kind `escalation`, node `route`). When there are no workflows at all, offer to set one up with the `customize-harness` skill. Never improvise a workflow.

## 2. Run the workflow
Load `H/workflows/<name>.yaml` and begin at `start`. On entering EVERY node, the first one and `ready` included, first run `H/skills/work/trace.sh <workflow> <id>`. It records the path and refuses a move that isn't an edge of the workflow, or a move on from a role node whose diff wasn't checked. If it refuses, fix the cause; never work around it. Never skip a node because a task looks small: sizing is already in the workflow's edges. Then:
- Read its `step:` file and every file in that step's `read:` list.
- **`role: <r>`:** delegate (section 4) to a FRESH agent. Give it:
  - its brief `H/roles/<r>.md` and the files in the brief's `read:` list;
  - its knowledge `H/knowledge/roles/<r>/INDEX.md`;
  - the step;
  - the spec;
  - the base commit.

  With `fan_out`, start one fresh agent per lens, never merging lenses. Run section 3 after EVERY role agent, fan-out agents included.
- **`human: true`:** ask the human with the fixed block, kind `review` (escalation.md), and wait.
- **`skill: <s>`:** use that skill for the step.
- **No `role:`** (e.g. verify, sanitize, handover): do the step yourself. Never delegate it, and never skip it.

Then choose the edge:
1. Check `next` in order. The first edge whose `when` holds wins; the last edge is the default.
2. **Limits:** an edge's `max` (or `defaults.max` for an automatic edge back to an earlier node) caps how often you take it for the same problem. If taking it again would exceed the cap, go to `defaults.on_exhaust` instead.

Special nodes:
- **`escalate`:** emit the block (kind `escalation`, with the asking node), wait for the answer, then resume the node that asked (`return: caller`).
- **`handoff: <wf>`:** continue in that workflow at its start, carrying the spec.
- **`terminal`:** run `trace.sh` for it, then end with the handover written by the step before it as your final message.

## 3. Role boundaries
1. Before each role, commit pending work so the tree is clean. Record `base=$(git rev-parse HEAD)`.
2. After the role returns, run `H/skills/work/check-diff.sh H/roles/<r>.md "$base"`. It reads `may_change` from the brief.
3. **On a violation:** run `git reset --hard "$base" && git clean -fd`, then re-run the role with the violation quoted. A second violation: escalate.
4. Otherwise, commit the role's work: `git add -A && git commit -m "<node>: <summary>"`.

## 4. Delegation per tool
Every role agent starts with a FRESH context and runs in the foreground: wait for its result before choosing the edge. Never end your turn while a role agent runs; only human nodes and escalations end a turn before `ready`. Its prompt is: "You are the <r>. Read <brief path> and follow it." followed by the inputs listed in section 2.
- **Claude Code:** Agent (Task) tool, `subagent_type: general-purpose`, not in the background.
- **opencode:** `task` tool, `subagent_type: general`.
- **omp:** `task` tool, agent `task`.
- **pi:** no subagents. Spawn `pi -p --no-session "<prompt>"` through bash. If that fails, play the role yourself, sequentially: re-read the brief and work only from the spec.

## Never
Never merge, deploy, push, or post to people unless a step says so and the human approved it. Escalate only by escalation.md and the owner rules in `H/instructions/global.md`.
