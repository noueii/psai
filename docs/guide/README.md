# Guide

For people who use psai and build stacks. (psai's own design decisions are in [../decisions/](../decisions/README.md).)

- **[Tutorial: build your first stack](tutorial.md).** Install psai, let `customize-harness` bootstrap a workflow, add a role, a guide, a template, a skill and rules, set a model, check it, publish by pushing, install it as a consumer in Claude Code, pi, omp and opencode, and keep it updated.
- **[Reference](reference/README.md).** One page per kind of file: the stack, workflows, steps, roles, guides, templates, rules, the shared skill and refs, skills, simulator cases and scenarios, knowledge and the stage, the fixed block.

## How psai works, in one minute
- **The nudge.** Each tool's channel injects a short always-on text: the Claude Code plugin's SessionStart hook, the pi and omp extension, or opencode's `instructions`. It tells the agent to use `request-router` first.
- **`request-router`** loads every `*-rules` skill, lists the `workflow-*` skills, and either runs a matching workflow, offers to set one up (a repeatable task with none), or handles a one-off directly.
- **`work`** runs the workflow node by node: a fresh agent per role, the role's diff checked against `may_change` (`check-diff.sh`), every move checked against the workflow (`trace.sh`), loop limits, one fixed escalation block, a final report, then the retro.
- **`customize-harness`** builds and changes your stack with you, one question at a time, in a worktree of your stack's clone (`$PSAI_STACK`).
- **`capture-knowledge`** writes findings to your stack's inboxes; **`retro`** turns what a task taught into one PR on your stack; **`sync`** fast-forwards your stack and updates everything through each tool's channel.

Nothing runs in the background, and psai has no CLI: the agent reads files and runs git and gh.
