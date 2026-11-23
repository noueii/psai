# psai

> **Archived.** psai has been replaced by [noueii/garden](https://github.com/noueii/garden), which builds on what was learned here (the "seeds" standard).


A workflow harness made of plain skills, for Claude Code, opencode, pi, omp and any agent that reads Agent Skills. psai gives your agents a request router, a workflow engine (fresh role agents, diff limits checked by script, loop limits, one fixed escalation format, a final report), knowledge capture, retros and sync. It ships no workflows: `customize-harness` builds yours with you, as skills, in your own **stack** (a skills repo you own). No CLI, no runtime, no build step: the repo is the package. **Start here: [the tutorial](docs/guide/tutorial.md)** (build, publish and install a stack) and [the reference](docs/guide/reference/README.md). Design: [docs/decisions/0012-skills-only.md](docs/decisions/0012-skills-only.md).

## Install
Pick one channel per tool; installing two gives you every skill twice. A plugin or package updates through its tool; `npx skills` copies files you update by hand.

| Tool | Install | Update |
|---|---|---|
| Claude Code | `claude plugin marketplace add noueii/psai` then `claude plugin install psai@psai` | `claude plugin marketplace update psai && claude plugin update psai@psai` |
| pi | `pi install https://github.com/noueii/psai` | `pi update --extensions` |
| omp | `omp plugin install https://github.com/noueii/psai` | the same command again |
| opencode | `npx skills add noueii/psai -g -a opencode`, then add the nudge to `opencode.json` (below) | `npx skills update -g` |
| any other agent | `npx skills add noueii/psai -g` | `npx skills update -g` |
| development | clone, then `scripts/link-skills.sh` (symlinks into `~/.claude/skills` and `~/.agents/skills`) | `git pull` |

The Claude Code plugin, the pi package and the omp plugin also inject a short always-on **nudge** ([skills/request-router/nudge.md](skills/request-router/nudge.md)) that sends every request through `request-router`. Elsewhere, add it yourself: in opencode, `"instructions": ["~/.agents/skills/request-router/nudge.md"]` in `opencode.json` (where `npx skills add -g` copies it); in any tool with a global instructions file, paste or import it there. The repo is also an [Agent Plugins](https://agent-plugins.org) package (`plugin.json`), for tools that read that format.

## Use it
1. Give an agent a task. With no workflow yet, `request-router` offers to set one up.
2. `customize-harness` interviews you one question at a time, then builds the workflow as a skill in your stack: a git repo at `$PSAI_STACK` (default `~/psai-stack`) that it scaffolds on first use, with its own install manifests and CI. Changes are staged in a worktree of it and arrive as one PR for you to merge.
3. Install your stack like psai (same channels), and from then on `request-router` picks the workflow, `work` runs it, and `retro` turns what the task taught into a PR on your stack.

## Skills
- `request-router`: decides each request: run a workflow (a skill named `workflow-*`), offer to set one up, or handle a one-off directly.
- `work`: the engine, read once a workflow is chosen. Runs it node by node, checks role diffs (`check-diff.sh`) and moves (`trace.sh`), escalates with the fixed block, writes the report.
- `customize-harness`: scaffolds your stack and builds or changes workflows, roles, steps, guides, templates, rules and skills with you.
- `capture-knowledge`: records facts, decisions and proposed rules in your stack's inboxes.
- `retro`: at the end of a task, ranks findings and stages changes to your stack as one PR.
- `sync`: fast-forwards your stack and updates psai and your stacks through each tool's channel.

## Stacks
A stack is a skills repo in the same layout as psai: workflows (`skills/workflow-<stack>-<name>/`), shared roles, guides and templates (`skills/<stack>-shared/`), always-on rules (`skills/<stack>-rules/`), your own skills, and the same manifests, so it installs through the same channels. Install as many as you like: each tool merges their skills. Prefix every skill with the stack's name to avoid collisions.

## Repo layout
```
skills/                    the six skills (all that users get)
.claude-plugin/            plugin.json and marketplace.json: the Claude Code plugin
hooks/hooks.json           the plugin's SessionStart hook: prints the nudge
extensions/psai.ts         the pi and omp extension: appends the nudge
plugin.json                the Agent Plugins manifest
package.json               the pi package ("pi"), which omp also reads
scripts/                   maintainer-only: check.sh, check.py, workflows.py (refs, graph rules, simulator), link-skills.sh,
                           prove-tutorial.sh (+ git-http.py, fake-model.py): the consumer-install proof
.github/workflows/         CI: scripts/check.sh --upstream on every PR
evals/                     maintainer-only: AI evals and test stacks
docs/guide/                the tutorial and the reference, for people
docs/decisions/            ADRs about psai itself
```

## Maintainers
See [AGENTS.md](AGENTS.md). `scripts/check.sh --upstream` runs the checks; nothing in `scripts/` or `evals/` ships to users.
