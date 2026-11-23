---
name: work
description: "The workflow engine: runs a chosen workflow skill node by node with fresh role agents, checked diff limits, loop limits, escalations and a final report. Use when request-router has matched a request to a workflow (a skill named workflow-*), before doing any of the work yourself."
---

# work

A workflow is a skill named `workflow-<name>`. Its folder `W` holds `workflow.yaml` (the source of truth: this skill only says how to run it) and the files it names. `request-router` picks the workflow; if you got here without routing, run it first. Never improvise a workflow.

**Refs.** A file named in a workflow, step or role is `path`, relative to the folder of the skill that holds the naming file, or `skill:path`, the file `path` in the folder of the skill `skill`. To find a skill's folder, load that skill the way your tool loads skills: its folder is where its SKILL.md is. Below, `work/` means this skill's folder.

## 1. Run the workflow
Load the workflow skill, read `W/workflow.yaml` and begin at `start`. On entering EVERY node, the first one and the terminal one included, run `bash work/trace.sh "$W" <node>` from the task's repo. It records the path and refuses a move that isn't an edge of the workflow, or a move on from a role node whose diff wasn't checked. If it refuses, fix the cause; never work around it. Never skip a node because a task looks small: sizing is already in the workflow's edges. Then:
- Read the node's `step` and every file in the step's `read:`.
- **`role: <ref>`:** delegate (section 3) to a FRESH agent. Give it:
  - the role file (its brief) and the brief's `read:` files;
  - its knowledge: `knowledge/roles/<role>/INDEX.md` in your stack (the `work` skill's `your-stack.md`), when it exists;
  - the step, the spec and the base commit;
  - its skills: the role's and the step's `skills: {required, optional}`. A required skill you can't see in your tool: don't start the role; escalate from this node, offering to install it with `customize-harness`. A missing optional skill goes in the final report.

  With `fan_out: [lens, ...]`, start one fresh agent per lens, never merging lenses. Run section 2 after EVERY role agent, fan-out agents included.
- **`human: true`:** ask the human with the fixed block, kind `review` (`work/escalation.md`), and wait.
- **`skill: <name>`:** use that skill for the step (`retro`, `sync`, or any other). A skill node may have no `step`.
- **No `role`** (running checks, writing the report): do the step yourself. Never delegate it, and never skip it.

Then choose the edge:
1. Check `next` in order. The first edge whose `when` holds wins; the last edge is the default.
2. **Limits:** an edge's `max` (or `defaults.max` for an automatic edge back to an earlier node) caps how often you take it for the same problem. If taking it again would exceed the cap, go to `defaults.on_exhaust` instead.

Special nodes:
- **`escalate`:** emit the block (kind `escalation`, with the asking node), wait for the answer, then resume the node that asked (`return: caller`).
- **`handoff: <workflow skill>`:** continue in that workflow at its start, carrying the spec.
- **`terminal`:** run `trace.sh` for it. If this run passed no `retro` node, run the `retro` skill now (always: it's how the harness learns). Then end with the final report written by the step before it, plus the retro's `## Retro` section, as your final message.

## 2. Role boundaries
1. Before each role, commit pending work so the tree is clean, and record `base=$(git rev-parse HEAD)`.
2. After the role returns, run `bash work/check-diff.sh <role file> "$base"`. It reads `may_change` from the role file.
3. **On a violation:** `git reset --hard "$base" && git clean -fd`, then re-run the role with the violation quoted. A second violation: escalate.
4. Otherwise commit the role's work: `git add -A && git commit -m "<node>: <summary>"`.

## 3. Delegation per tool
Every role agent starts with a FRESH context and runs in the foreground: wait for its result before choosing the edge. Never end your turn while a role agent runs; only human nodes and escalations end a turn before the terminal node. Its prompt starts: "You are the <role> inside a running workflow. Do not run request-router or work, and do not start workflows. Do your brief and return. Read <role file> and follow it." Then come the inputs listed in section 1. A role may still use capture-knowledge and the skills its brief lists.

**Model:** the role file's `model:` is a tier (`fast`, `balanced`, `strong`) or ids per tool (`{claude: opus, pi: <provider/id>}`). Pass it where your tool can; where it can't, or none is set, use the current model and write "model not set: <tool>" in the final report.
- **Claude Code:** the Agent tool, `subagent_type: general-purpose`, `model`: the `claude` id, else the tier as `haiku`, `sonnet` or `opus`. Not in the background.
- **opencode:** the `task` tool, `subagent_type: general` (no model per call).
- **omp:** the `task` tool, agent `task` (no model per call).
- **pi:** no subagents. Run `PSAI_ROLE=<role> pi -p --no-session [--model <pi id>] "<prompt>"` through bash (`PSAI_ROLE` turns off the nudge). If that fails, play the role yourself, sequentially: re-read the brief and work only from the spec.

## Never
Never end a turn with a plain question: ask only with the fixed block. Never merge, deploy, push, or post to people unless a step says so and the human approved it; the retro's and sync's one PR to your own stack is the exception. Escalate only by the fixed block and the rules your stack's `*-rules` skill lists.
