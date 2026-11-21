# 0002: One repo, four tools, one installer (2026-11-21)
- Decision: skills are linked into `~/.claude/skills` (Claude Code) and `~/.agents/skills` (opencode, pi, omp). `global.md` is imported (Claude Code, omp) or inlined between markers (pi, opencode). Install only for tools whose config folder exists; never clobber; back up before a first edit.
- Why: verified per tool in the v1 research (formats facts file). opencode reads both skill folders, so it loads each skill once and logs a duplicate warning. Folder detection is deterministic and testable.
- Source: the owner's v1 brief; v1 PR #1.
