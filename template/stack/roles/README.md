# roles/

Who an agent is when a `role:` node starts it, and what it may touch. Each role gets a fresh agent and its own knowledge in `knowledge/roles/<role>/INDEX.md` (create it with the role). Name: `<role>.md`. Example: psai's test stack, `evals/fixtures/stacks/example/roles/checker.md`.

Format:
```md
---
may_change: nothing        # anything | tests | nothing; enforced by psai check-diff
read: [guides/example-rules.md]   # this stack's files; another stack's exported ones as other:guides/x.md
skills:                    # optional; by name. The step's skills add to the role's.
  required: [change-notes] # missing -> work escalates, offering to install it
  optional: []             # missing -> noted in the final report
model: balanced            # optional: fast | balanced | strong, or {claude: opus, pi: <id>, ...}
---
# Role: checker
Workflow, rules, what to return, and where its knowledge is.
```
Never list `request-router` or `work`: a role doesn't route. Prefix your skills' names with the stack's (`acme-changelog`): the tools' skill folders are flat.
