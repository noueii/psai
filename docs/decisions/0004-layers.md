# 0004: Layers and who writes them (2026-11-21)
- Decision:
  - skill = how the machinery runs;
  - role = who I am and what I may touch;
  - step = what happens here;
  - guide = how this kind of work is done;
  - template = the exact output format;
  - knowledge = what's true and what was decided.

  During a task, agents write only to knowledge inboxes and the task's PR description or handover. Everything else changes only through `customize-harness`, as a PR the owner approves. v1's preferences became guides (rules), and knowledge became facts, decisions and inboxes.
- Why: rules and facts age differently and need different owners; agents must not rewrite their own rules mid-task.
- Source: the owner's v2 spec.
