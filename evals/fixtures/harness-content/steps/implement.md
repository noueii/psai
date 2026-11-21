---
read: [guides/coding-rules.md]
---
# Implement

**In:** the spec and the base commit, plus any failing check output or review findings when sent back. **Out:** the change, and the Engineer's report.

The Engineer implements the smallest change that meets the acceptance criteria. When sent back, it fixes the reported failures or findings first, and only those.

**Edges:**
- `checks exist and the spec is unchanged`: QA already ran in an earlier round of THIS task (verify_prep), and the spec hasn't changed since. Tests the Engineer wrote don't count.
- Otherwise `no checks yet or the spec changed`. This is always the edge on the first pass, so QA writes or updates checks.
