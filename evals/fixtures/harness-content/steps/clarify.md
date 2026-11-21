---
read: [templates/spec.md]
---
# Clarify and size

**In:** the task. **Out:** a spec (templates/spec.md) and a size.

1. Read the task, the repo's rules (AGENTS.md, CLAUDE.md, CONTRIBUTING, `.harness/`) and the knowledge index.
2. Write the spec: goal, acceptance criteria, out of scope. Fill gaps yourself where code and docs settle them, and note those choices as decisions.
3. Size it:
   - **small**: clear, low-risk, contained;
   - **big**: multi-repo, API/schema/data changes, unclear or risky.

**Edges:**
- `blocking question`: a requirement is unclear AND the answer changes the outcome, and code, docs and knowledge can't settle it.
- Otherwise `big` or `small`.
