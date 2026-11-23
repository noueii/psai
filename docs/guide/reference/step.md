# A step

`steps/<name>.md` in a workflow's folder: what happens at one node.

```md
---
read: [acme-shared:guides/style.md, templates/report.md]
skills: { optional: [acme-changelog] }
---
# Report

**In:** the change and the test results. **Out:** the final report.

Write the report (templates/report.md) as your final message.

**Edges:** `blocked` when ...; otherwise the default.
```
- `read:` lists refs read with the step (guides, templates). Optional.
- `skills:` lists `required` and `optional` skills for whoever runs the step.
- In the prose, say what comes in and what goes out, and when each named edge (`when:`) applies.
