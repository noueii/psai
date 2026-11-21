# steps/

What happens at one point of a workflow. A workflow node points here with `step:`. Name: `<verb-or-noun>.md`, matching the node's job (`clarify.md`, `verify-prep.md`). Example: [evals/fixtures/harness-content/steps/verify-prep.md](../evals/fixtures/harness-content/steps/verify-prep.md).

Format: frontmatter `read:` lists the guides and templates to load with the step (paths from the harness root), then the instructions in full prose: inputs, what to do, outputs, and which outcome selects which edge.
```md
---
read: [guides/testing-rules.md]
---
# Verify prep
...
```
