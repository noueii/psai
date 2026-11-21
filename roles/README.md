# roles/

Who an agent is when a `role:` node starts it, and what it may touch. Each role gets a fresh agent and its own knowledge in `knowledge/roles/<role>/`. Name: `<role>.md`. Example: [evals/fixtures/harness-content/roles/checker.md](../evals/fixtures/harness-content/roles/checker.md).

Format:
```md
---
may_change: nothing        # anything | tests | nothing; enforced by skills/work/check-diff.sh
read: [guides/example-rules.md]
skills:                    # optional; by name. The step's skills add to the role's.
  required: [change-notes] # missing -> work escalates, offering to install it
  optional: []             # missing -> noted in the final report
---
# Role: checker
Workflow, rules, what to return, and where its knowledge is.
```
`work` resolves the skills with `scripts/harness.py skills brief` and lists them in the role agent's brief. Never list `request-router` or `work`: a role doesn't route. Where a skill goes (my-skills/, skills.yaml, a repo's `.agents/skills/`): LAYOUT.md.
