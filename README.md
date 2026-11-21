# psai

My tool-agnostic agent harness: skills, role briefs, knowledge and an installer for Claude Code, opencode, pi and oh-my-pi (omp). Inspired by [mattpocock/skills](https://github.com/mattpocock/skills), with two differences: every skill is model-invoked (agents run on their own), and the work loop uses roles.

## What's in it
- `instructions/global.md`: the always-loaded core: principles, escalation policy, the loop, where knowledge lives.
- `skills/` (flat, all model-invoked):
  - `task-loop`: the loop for any task (clarify, size, implement, QA, verify, review, sanitize), delegation per tool, and role boundary checks. Role briefs live in `task-loop/roles/`.
  - `capture-knowledge`: when and how to record a preference or decision, and how to promote it by PR.
  - `sanitize-pr`: pre-merge cleanup against the owner's preferences and the repo's rules.
- `knowledge/`: shared preferences, decisions and inbox, plus one folder per role.

## Install
```sh
git clone <this repo> ~/workspace/github.com/noueii/psai
~/workspace/github.com/noueii/psai/install.sh --dry-run   # see what it would change
~/workspace/github.com/noueii/psai/install.sh
```
It installs only for tools whose config folder exists (`~/.claude`, `~/.config/opencode`, `~/.pi/agent`, `~/.omp/agent`):
- links `~/.harness` to the clone;
- links each skill into `~/.claude/skills` (Claude) and `~/.agents/skills` (opencode, pi, omp). It never replaces a skill that isn't its own;
- adds one line, `@~/.harness/instructions/global.md`, to `~/.claude/CLAUDE.md` and `~/.omp/agent/AGENTS.md`;
- inlines `global.md` between `<!-- harness:start -->` and `<!-- harness:end -->` in `~/.pi/agent/AGENTS.md` (or the `CLAUDE.md` pi already uses) and `~/.config/opencode/AGENTS.md`, since those have no imports.

Before its first edit of an existing file it saves `<file>.harness-backup`.

opencode reads both skill folders, so it finds each skill twice. It loads one copy and logs a `duplicate skill name` warning. To silence the warning, set `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`; the installer doesn't touch your shell profile.

## Update
```sh
git -C ~/.harness pull --autostash && ~/.harness/install.sh
```
Skills and imported instructions update with the pull. Re-running the installer refreshes the inlined copies (pi, opencode) and links new or renamed skills. `--autostash` keeps local knowledge inbox entries.

## Uninstall
```sh
~/.harness/install.sh --uninstall
```
It removes its links, its import line and its marked blocks, and deletes files it created that are now empty. Backups are kept.

## Check
```sh
scripts/check.sh             # frontmatter, role boundaries, installer tests in temp HOMEs
scripts/check.sh --discover  # also asks opencode, pi and omp which skills they see
```
