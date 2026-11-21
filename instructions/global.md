# psai harness

- Ask a human only with the fixed block in `skills/work/escalation.md`. Otherwise decide, and log what you decided.
- Change the owner's setup (workflows, steps, roles, guides, templates, owner rules) only with `customize-harness`, which stages it. During a task, write only to knowledge inboxes (`capture-knowledge`) and the task's own report; nothing goes to GitHub. At the end, the `retro` skill turns what was staged into one PR the owner merges.
- Precedence, most specific wins: the current step or role > owner rules > this text. A repo's own rules live in its AGENTS.md or docs.
