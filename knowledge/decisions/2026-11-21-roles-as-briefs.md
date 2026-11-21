# 2026-11-21: Roles are briefs inside skills

- Decision: Engineer, QA and Reviewer are role briefs in `skills/task-loop/roles/`, handed to a fresh subagent by the loop skill. Delegation: Claude Code's Agent tool (general-purpose), the `task` tool in opencode and omp, and a fresh `pi -p` process in pi (sequential fallback). Boundaries are enforced by checking each role's git diff (QA touches only tests and checks, Reviewer touches nothing), rejecting and re-running on violation.
- Why: the harness is tool-agnostic and must work in Claude Code, opencode, pi and omp; native agent files differ per tool (and pi has none), so they are a later, optional add-on.
- Source: owner's brief for harness v1.
