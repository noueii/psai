# roles/

Who an agent is when a `role:` node starts it, and what it may touch. Each role gets a fresh agent and its own knowledge in `knowledge/roles/<role>/`. Name: `<role>.md`. Example: [evals/fixtures/harness-content/roles/qa.md](../evals/fixtures/harness-content/roles/qa.md).

Format:
```md
---
may_change: tests          # anything | tests | nothing; enforced by skills/work/check-diff.sh
read: [guides/testing-rules.md]
---
# Role: QA
Workflow, rules, what to return, and where its knowledge is.
```
