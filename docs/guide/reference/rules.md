# The rules skill

`skills/<stack>-rules/SKILL.md`: rules for every task, such as when to escalate or what to always log. `request-router` loads every `*-rules` skill before it picks a workflow. Your own stack's rules win over another stack's.

```md
---
name: acme-rules
description: "acme's rules for every task: when to escalate, what to log. Use when request-router starts on a request, before choosing a workflow."
---
- Escalate before deleting data or changing a public API.
- Log every decision taken alone in the final report.
```
Keep it to a few bullets: it is read on every task. A rule for one repo belongs in that repo's AGENTS.md, not here.
