---
name: sanitize-pr
description: "Pre-merge cleanup of a pull request against the owner's preferences and the repo's rules: diff hygiene, commits, title and description, decision log, checks. Use before marking a PR ready for review, before asking a human to merge, and after the last review round."
---

# Sanitize PR

Make the PR ready for a human to merge. Never merge it yourself.

## Inputs
- The repo's rules: AGENTS.md, CLAUDE.md, CONTRIBUTING, PR template, commit conventions, CI config.
- The owner's preferences: `~/.harness/knowledge/preferences/` and any relevant inbox entries.

Where the repo's rules and the owner's preferences conflict, escalate (see `task-loop/escalation.md`).

## Checklist
1. **Diff**: only in-scope changes. Remove debug output, commented-out code, stray files, unrelated formatting, TODOs without an owner.
2. **No secrets** or credentials, and no content that belongs to another repo or company.
3. **Commits**: follow the repo's convention (message format, squash or not, sign-off).
4. **Title and description**: follow the PR template if there is one. The description says what changed, why, and how it was verified.
5. **Decision log**: every decision made without escalating, with its reason, is listed in the description. Each one is also in the knowledge inbox.
6. **Checks**: CI and the QA checks pass on the final commit. Re-run them after any cleanup.
7. **Reviews**: every review comment has been addressed or answered; open questions are stated, not hidden.

Report what you changed and anything that still blocks a merge.
