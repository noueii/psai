# Harness: global rules

## Principles
- Work autonomously. Decide what you can settle from the code, docs and knowledge; escalate only by the policy below.
- Keep changes small and in scope. Prefer the repo's own rules and conventions.
- Never merge, deploy or post to people yourself.

## Escalation policy
Escalate only when:
- a requirement is unclear AND the answer changes the outcome, and code, docs and knowledge can't settle it;
- the action is irreversible or visible to others (merge, deploy, posting to people, deleting what isn't yours);
- it goes against a stated rule or preference, or two rules conflict;
- you're still stuck after two real attempts;
- the scope grows well beyond what was asked.

Otherwise decide, and log the decision and its reason in the PR description and the knowledge inbox.

## The loop
For any task that changes code, docs or config, use the `task-loop` skill: clarify, size, implement (Engineer), verification prep (QA), verify, AI review then human review, sanitize the PR (`sanitize-pr`). Never merge.

## Knowledge
Plain Markdown in `~/.harness/knowledge/`. Read `INDEX.md` on demand, not up front.
- Shared: `preferences/`, `decisions/`, `inbox.md`.
- Per role: `roles/<engineer|qa|reviewer>/`.

When you learn a preference or make a decision worth keeping, use the `capture-knowledge` skill.
