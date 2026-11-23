# The shared skill and refs

`skills/<stack>-shared/`: roles, guides and templates that several workflows use. Its SKILL.md lists them, so an agent that loads it knows what's inside.

```md
---
name: acme-shared
description: "Roles, guides and templates that acme's workflows share. Use when a workflow, step or role names a file in acme-shared."
---
- `roles/tester.md`: adds tests from the task; may change tests.
- `guides/style.md`: house style for prose.
```

## Refs
Anything a workflow, step or role names is a ref:
- `path`: in the folder of the skill holding the naming file (`steps/do.md`, `roles/maker.md`);
- `skill:path`: in the folder of the skill `skill` (`acme-shared:roles/tester.md`).

The agent finds a skill's folder by loading the skill the way its tool does: wherever the tool installed it, the folder is where its SKILL.md is. A stack may name files in another stack's skills the same way (`other-shared:guides/x.md`); its README should say that stack is needed, and its CI checks it with `--with`.
