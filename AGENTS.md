# Maintaining psai

psai ships VANILLA and is meant to be forked: the machinery plus empty, documented folders. Never ship a file in a user-owned place (LAYOUT.md, Owner = you), nor anyone's personal setup. Test content stays neutral, in `evals/fixtures/harness-content/`. psai's own scenarios go in `evals/scenarios/psai/`, and decisions about psai itself go in `docs/decisions/`.

## Rules
- **Every line costs context.** `instructions/global.md` is at most 250 words, and SKILL.md files stay short: the workflow file is the source of truth.
- **Skills:**
  - flat `skills/<name>/SKILL.md`, with `name` equal to the folder name;
  - quoted `description` saying what the skill does and "Use when ...";
  - all model-invoked: never `disable-model-invocation`;
  - no paths into `~/.psai` or `$PSAI_HOME`: find files by name with `psai resolve` (and `psai route`, `psai node`); only the plugins' `psai-bootstrap` lines know the home.
- **Placement:** every folder has a README.md (what belongs there, format and naming, one example). Files go where LAYOUT.md says. A new kind of file needs a LAYOUT row first.
- **Formats:**
  - workflows: workflows/README.md;
  - steps and roles: frontmatter `read:`, plus `may_change:` for roles;
  - the fixed escalation block: skills/work/escalation.md.
- **Delegation:** anything that delegates starts a FRESH agent and covers Claude Code, opencode, omp and pi.
- **Installer:**
  - idempotent; supports `--dry-run` and `--uninstall`;
  - touches only its own links, import line and marked block;
  - backs up a file before its first edit, and installs only for tools that are present.
  - Never run it against the real HOME while testing.

## Before committing
Run `scripts/check.sh --upstream` (add `--discover` after installer or layout changes). Run `evals/run.sh` after changing `work`, `customize-harness` or the fixtures, and keep the AI evals small.
