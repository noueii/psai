---
read: [guides/pr-description.md]
---
# Sanitize

**In:** the branch, the repo's rules, the owner's guides. **Out:** a branch a human can merge.

1. **Diff:** only in-scope changes. Remove debug output, commented-out code, stray files and unrelated formatting.
2. **Safety:** no secrets, and no content that belongs to another repo or company.
3. **Commits:** follow the repo's convention.
4. **PR:** if a PR exists, its title and description follow `guides/pr-description.md`.
5. **Checks:** re-run every check on the final commit.

Never merge.

**Edges:**
- `a check broke`: go back to verify.
- Otherwise `clean`.
