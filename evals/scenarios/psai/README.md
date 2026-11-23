# evals/scenarios/psai/

psai's own scenarios. They run on neutral test content and never encode anyone's setup:
- `vanilla-no-workflow`: a repeatable task with psai alone escalates and offers `customize-harness`;
- `happy-path`, `ambiguous`, `boundary`: L3, with the test stack `example` loaded;
- `routes-unnamed`, `quick-question`, `repeatable-unmatched`: L3 routing (a match the request doesn't name, a one-off, a repeatable task with no workflow);
- `role-skill`, `missing-skill`: L3 role skills (the doer requires `example-change-notes`: it is listed in the brief and used; when it is missing, work escalates from `do` offering to install it);
- `retro`, `retro-sync`: L3 task end. With no sync node, work still runs the retro: ranked findings, ONE local `psai/` branch in the owner's stack, and sync never runs. With a `report → retro → sync → ready` tail (`variants/sync-tail`), sync finishes the stage instead;
- `role-model`: the checker has `model: fast` (`variants/model-tier`), so Claude Code delegates it with `haiku`;
- `customize-asks-stack`: adding a piece, customize-harness asks which stack first, then stages it in the owner's stack;
- `two-stacks`: two stacks loaded; a note-sorting request goes to `workflow-other-triage`;
- `bootstrap`: L4, from no stack through `customize-harness` (scaffold, interview, workflow as skills) to a fixture task.

Format: [../README.md](../README.md). Example: [happy-path.yaml](happy-path.yaml).
