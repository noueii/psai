# steps/

What happens at one point of a workflow. A workflow node points here with `step:`. Name: `<verb-or-noun>.md`, matching the node's job (`do.md`, `check.md`). Example: psai's test stack, `evals/fixtures/stacks/example/steps/do.md`.

Format: frontmatter `read:` lists the guides and templates to load with the step (this stack's paths, or `other:guides/x.md` for a file another stack exports), and the optional `skills: {required: [...], optional: [...]}` adds skills, by name, to the role's for this step. Then come the instructions in full prose: inputs, what to do, outputs, and which outcome selects which edge.
```md
---
read: [guides/example-rules.md]
---
# Do
...
```
