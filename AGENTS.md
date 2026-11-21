# Maintaining this repo

These files load into every agent session, so every line costs context. Keep them short and plain.

## Skills
- Flat layout: `skills/<name>/SKILL.md`. `name` equals the folder name, lowercase with hyphens.
- Frontmatter has `name` and `description` only. Quote the description.
- Every skill is model-invoked. Never add `disable-model-invocation`, slash commands or user-only triggers.
- The description says what the skill does and precisely when to use it ("Use when ...").
- Keep `SKILL.md` short. Move detail into sibling files the skill links to (like `task-loop/roles/`).
- Paths inside skills use `~/.harness/...`, never a clone path.
- A skill that delegates says to start the subagent with a fresh context, and covers Claude Code, opencode, omp and pi.

## Roles
Roles are briefs in `skills/task-loop/roles/`, not native agent files. Each has its own workflow, rules and knowledge folder (`knowledge/roles/<role>/`). Boundaries are enforced by `skills/task-loop/check-diff.sh`.

## Knowledge
- Plain Markdown. `preferences/` and `decisions/` hold only what the owner stated or decided; mark anything inferred as inferred.
- Decision files are `decisions/YYYY-MM-DD-<slug>.md` with Decision, Why and Source.
- Inbox entries change only locally; promotion to topic files goes through a PR that the owner merges.
- No company-specific content (it stays in that company's repos), no secrets.

## Installer
- `install.sh` stays idempotent, supports `--dry-run` and `--uninstall`, touches only its own links, import line and marked block, backs up before a first edit, and installs only for tools that are present.
- Never run it against the real HOME while testing; `scripts/check.sh` uses temp HOMEs.

## Before committing
Run `scripts/check.sh` (add `--discover` when the installer or skill layout changed). Update `README.md` and `knowledge/INDEX.md` when you add or rename something.
