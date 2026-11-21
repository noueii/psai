# skills/

The ONLY things the tools discover. Flat: `skills/<name>/SKILL.md`, where `name` equals the folder name; all are model-invoked (never `disable-model-invocation`). Supporting files sit next to `SKILL.md`. Example: [work/SKILL.md](work/SKILL.md).

- `request-router`: decides each request: run a workflow, offer to create one, or handle a one-off directly. The injected nudge tells agents to run it first.
- `work`: the engine, read once a workflow is chosen. Runs it, checks role diffs, escalates, writes the report.
- `customize-harness`: builds and changes the owner's setup with them, starting from vanilla.
- `capture-knowledge`: records facts, decisions and proposed rules in the inboxes; the retro promotes them.
- `retro`: at the end of a task (work always runs it after a workflow), reviews the run, ranks findings, files each where it belongs (your overlay, a stack you author, or a suggestion for another stack's author) and stages one PR per repo.
- `sync`: runs only where a workflow has a `sync` node, or when asked: out-of-sync check, fast-forward update of your overlay and the framework, newer stack releases, drift adoption, one PR per repo you own.
