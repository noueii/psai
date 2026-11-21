# 0002: One repo, four tools, one installer (2026-11-21)
- Decision: skills are linked into `~/.claude/skills` (Claude Code) and `~/.agents/skills` (opencode, pi, omp). Always-on text reaches each tool through exactly one plugin (see 0008). Install only for tools whose config folder exists; never clobber; back up before a first edit.
- Why: verified per tool against the installed versions. opencode reads both skill folders, so it loads each skill once and logs a duplicate warning. Folder detection is deterministic and testable.
- Source: v1 and v2 design.
- Note (2026-11-21): the base link was renamed from `~/.harness` to `~/.psai` (override: `PSAI_HOME`). The installer removes an old `~/.harness` link to a psai clone on upgrade; text above that predates the rename means `~/.psai`.
