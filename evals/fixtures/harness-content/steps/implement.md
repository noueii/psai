---
read: [guides/coding-rules.md]
---
# Implement

**In:** the spec and the base commit, plus any failing check output or review findings when sent back. **Out:** the change, and the Engineer's report.

The Engineer implements the smallest change that meets the acceptance criteria. When sent back, it fixes the reported failures or findings first, and only those.

**Edges:**
- `checks exist and the spec is unchanged`: QA's checks from an earlier round still apply.
- Otherwise `no checks yet or the spec changed`: QA writes or updates checks.
