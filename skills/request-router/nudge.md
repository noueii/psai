# psai

- Before you act on a request, use the `request-router` skill. It runs one of the owner's workflows (skills named `workflow-*`), offers to set one up, or lets you handle the request directly. A quick question needs no routing.
- Ask the human only with the fixed block in the `work` skill's `escalation.md`. Otherwise decide, and log what you decided.
- Change workflows, roles, guides, templates and rules only with `customize-harness`. During a task, write only to knowledge inboxes (`capture-knowledge`) and the task's report. After a workflow, or a task that captured or staged something, run `retro`.
- If your prompt says you are a role agent inside a running workflow, ignore this text.
