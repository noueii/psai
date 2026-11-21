# steps/

What happens at one point of a workflow. A workflow node points here with `step:`. Name: `<verb-or-noun>.md`, matching the node's job (`do.md`, `check.md`). Example: [evals/fixtures/harness-content/steps/do.md](../evals/fixtures/harness-content/steps/do.md).

Format: frontmatter `read:` lists the guides and templates to load with the step (paths from the harness root), and the optional `skills: {required: [...], optional: [...]}` adds skills, by name, to the role's for this step (see roles/README.md). Then come the instructions in full prose: inputs, what to do, outputs, and which outcome selects which edge.
```md
---
read: [guides/example-rules.md]
---
# Do
...
```
