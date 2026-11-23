# Layout: where things go in a stack

A stack is a git repo of skills in the same layout as psai, so it installs through the same channels (`.claude-plugin/`, `plugin.json`, `package.json`). Your own stack is the clone at `$PSAI_STACK` (the `work` skill's `your-stack.md`). `<stack>` is the stack's name (the manifests' `name`): **every skill a stack ships starts with it** (or with `workflow-<stack>-`), so several stacks never collide. Formats: [FORMATS.md](FORMATS.md).

| You're adding | Goes in |
|---|---|
| a workflow | `skills/workflow-<stack>-<name>/SKILL.md` and `workflow.yaml` |
| its steps | `skills/workflow-<stack>-<name>/steps/<step>.md` |
| a role, guide or template only that workflow uses | `skills/workflow-<stack>-<name>/roles/<role>.md`, `guides/<guide>.md`, `templates/<template>.md` |
| a role, guide or template several workflows use | `skills/<stack>-shared/roles/`, `guides/`, `templates/` (and its SKILL.md, which lists them) |
| rules for every task (an escalation policy, a preference) | `skills/<stack>-rules/SKILL.md`: a few short bullets |
| a skill of the stack's own | `skills/<stack>-<name>/SKILL.md` and its files |
| a workflow diagram | `skills/workflow-<stack>-<name>/GRAPH.md` (optional; `graph.py` writes it) |
| simulator cases for a workflow | `evals/cases/workflow-<stack>-<name>.yaml` |
| an eval scenario | `evals/scenarios/<name>.yaml` |
| **your own stack only:** a finding during a task | `knowledge/inbox.md`, or `knowledge/roles/<role>/inbox.md` for one role |
| **your own stack only:** a promoted fact | `knowledge/facts/<topic>.md` |
| **your own stack only:** a promoted decision | `knowledge/decisions/YYYY-MM-DD-<slug>.md` |
| **your own stack only:** the knowledge index | `knowledge/INDEX.md` (and `knowledge/roles/<role>/INDEX.md`) |
| the install manifests | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugin.json`, `package.json` (same name and version) |
| CI | `.github/workflows/psai.yml` (from the template) |

- Only `skills/` ships to people who install the stack. `knowledge/` and `evals/` stay in the repo: knowledge is read from your own clone.
- Every folder outside `skills/<name>/` has a README.md; a skill's SKILL.md is its README.
- A rule for one repo only belongs in that repo's own AGENTS.md or docs, not in a stack.
- Never edit a stack someone else authors: copy the workflow into your stack under your own name.
