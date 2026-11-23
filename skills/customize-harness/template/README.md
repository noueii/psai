# __NAME__

__DESCRIPTION__

A [psai](https://github.com/noueii/psai) stack: workflows, roles, guides, templates and rules as skills. It needs psai installed in the same tool. Its skills all start with `__NAME__` (workflows with `workflow-__NAME__-`).

## Install
Install psai first (its README), then this stack through the same channel:

| Tool | Install | Update |
|---|---|---|
| Claude Code | `claude plugin marketplace add __REPO__` then `claude plugin install __NAME__@__NAME__` | `claude plugin marketplace update __NAME__ && claude plugin update __NAME__@__NAME__` |
| pi | `pi install https://github.com/__REPO__` | `pi update --extensions` |
| omp | `omp plugin install https://github.com/__REPO__` | the same command again |
| opencode, any other agent | `npx skills add __REPO__ -g` | `npx skills update -g` |
| development | clone, then `bash <customize-harness>/link-skills.sh <clone>` | `git pull` |

## Change it
Ask an agent to change a workflow: `customize-harness` stages the change in a worktree of your clone, and the retro opens one PR. CI (`.github/workflows/psai.yml`) runs psai's checks on every push. Publish by pushing (or tagging `vX.Y.Z`); bump the version in `.claude-plugin/plugin.json`, `plugin.json` and `package.json` together.

## Layout
`skills/` (what ships), `knowledge/` (the owner's knowledge, read from the clone), `evals/` (simulator cases and eval scenarios). See psai's `customize-harness` skill: `LAYOUT.md`, `FORMATS.md`.
