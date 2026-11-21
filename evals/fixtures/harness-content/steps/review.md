---
read: [guides/coding-rules.md, guides/testing-rules.md]
---
# Review

**In:** the spec, and the diff from the task's first base commit. **Out:** findings, most severe first, each classed as `small fix`, `rework` or `spec gap`.

- **At `ai_review`:** each Reviewer works through one lens. Apply `small fix` items yourself. Send `rework` back to the Engineer with the findings. Escalate a `spec gap`.
- **At `human_review`:** ask the human with a `review` block, summarising the change and the AI review, and treat their answer the same way. `approved` moves on.

**Edges:**
- `small fix`, `rework`, `spec gap`: as above.
- `clean` / `approved`: nothing left to address.
