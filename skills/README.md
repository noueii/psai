# skills/

The ONLY things the tools discover. Flat: `skills/<name>/SKILL.md`, where `name` equals the folder name; all are model-invoked (never `disable-model-invocation`). Supporting files sit next to `SKILL.md`. Example: [work/SKILL.md](work/SKILL.md).

- `work`: the engine. Routes a task, runs its workflow, checks role diffs, escalates, hands over.
- `customize-harness`: builds and changes the owner's setup with them, starting from vanilla.
- `capture-knowledge`: records facts, decisions and proposed rules in the inboxes; promotes them by PR.
