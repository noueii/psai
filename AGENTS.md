# Maintaining psai

psai is a skills-only pack (docs/decisions/0012-skills-only.md): everything users get is a skill in `skills/`, and the repo itself is the package for every tool's channel. It ships no content (no workflow, rules or shared skill, no knowledge/): `scripts/check.sh --upstream` fails otherwise. Test content stays neutral, in the test stacks in `evals/fixtures/stacks/`. psai's own scenarios go in `evals/scenarios/psai/`, and decisions about psai itself go in `docs/decisions/`.

## Rules
- **Every line costs context.** The nudge (`skills/request-router/nudge.md`) is at most 120 words, and SKILL.md files stay short: the workflow file is the source of truth.
- **No CLI, no runtime.** Skills tell the agent what to read and which git and gh commands to run. A script lives inside the skill that uses it, and only when it gives a real guarantee (`work/check-diff.sh`, `work/trace.sh`). Maintainer tooling (`scripts/`, `evals/`) never ships.
- **Skills:**
  - flat `skills/<name>/SKILL.md`, with `name` equal to the folder name;
  - frontmatter only from the Agent Skills set (`name`, `description`, `license`, `allowed-tools`, `metadata`, `compatibility`): Agent Plugins clients reject a skill with any other key;
  - quoted `description` saying what the skill does and "Use when ...", at most 1024 characters;
  - all model-invoked: never `disable-model-invocation`;
  - a skill names another skill's file as `skill:path` (or "the `work` skill's `escalation.md`"), never by an install path.
- **Placement:** every folder outside `skills/<name>/` has a README.md (what belongs there, format and naming, one example). A stack's layout is `skills/customize-harness/LAYOUT.md`; a new kind of stack file needs a row there first.
- **Formats:** content formats are `skills/customize-harness/FORMATS.md`; the fixed escalation block is `skills/work/escalation.md`; where your stack is, `skills/work/your-stack.md`.
- **Manifests:** `.claude-plugin/plugin.json`, `plugin.json` and `package.json` carry the same name and version; bump all three together. Keep the nudge files (`hooks/hooks.json`, `extensions/psai.ts`) to the one job of printing the nudge.
- **Delegation:** anything that delegates starts a FRESH agent and covers Claude Code, opencode, omp and pi.
- **Never install into the real HOME while testing:** use a temp HOME, as `scripts/check.sh` does.

## Before committing
Run `scripts/check.sh --upstream` (CI runs it too). Run `scripts/prove-tutorial.sh` after changing the tutorial, the manifests, the nudge files or the stack template. The AI evals (`evals/run.sh`) are optional and manual-only: never in CI, never required for a PR.
