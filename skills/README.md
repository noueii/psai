# skills/

Everything psai ships to users, and the only thing the tools discover. Flat: `skills/<name>/SKILL.md`, where `name` equals the folder name; all are model-invoked. Supporting files (and the scripts that give a real guarantee) sit next to the SKILL.md that uses them. Example: [work/SKILL.md](work/SKILL.md).

- `request-router`: decides each request: run a workflow (a skill named `workflow-*`), offer to set one up, or handle a one-off directly. Its `nudge.md` is the always-on text the plugins inject.
- `work`: the engine, read once a workflow is chosen; `escalation.md` (the fixed block), `your-stack.md` (where your stack, its knowledge and its stage are), `check-diff.sh`, `trace.sh`.
- `customize-harness`: scaffolds your stack (from `template/`) and builds or changes its content with you; `LAYOUT.md` (where things go in a stack), `FORMATS.md` (every content format), `patterns/`, `graph.py` (an optional diagram helper), `link-skills.sh` (links a clone for development).
- `capture-knowledge`: records facts, decisions and proposed rules in your stack's inboxes.
- `retro`: at the end of a task, ranks findings and stages changes to your stack as one PR.
- `sync`: fast-forwards your stack and updates psai and your stacks through each tool's channel.
