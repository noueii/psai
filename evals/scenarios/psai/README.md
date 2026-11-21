# evals/scenarios/psai/

psai's own scenarios (upstream-owned). They run on neutral test content and never encode anyone's setup:
- `vanilla-no-workflow`: a task on vanilla escalates and offers `customize-harness`;
- `happy-path`, `ambiguous`, `boundary`: L3, on `evals/fixtures/harness-content/`;
- `routes-unnamed`, `quick-question`, `repeatable-unmatched`: L3 routing (a match the request doesn't name, a one-off, a repeatable task with no workflow);
- `role-skill`, `missing-skill`: L3 role skills (the doer requires `change-notes`: it is listed in the brief and used; when it is missing, work escalates from `do` offering to install it);
- `retro`, `retro-sync`: L3 task end. Without a sync node, work still runs the retro: ranked findings and ONE local `psai/retro-` branch, and sync never runs. With a `report → retro → sync → ready` tail (`content: [harness-content, sync-tail]`), exactly one local `psai/sync-` branch and no retro branch;
- `role-model`: L3 model per role: the checker has `model: fast` (fixture `model-tier`), so Claude Code delegates it with `haiku`;
- `customize-asks-stack`: L3: changing an installed stack's rule, customize-harness asks which stack first and stages an override in the overlay;
- `two-stacks`: L3 routing across stacks (ADR 0011): a stacks-layout home with `example` and `other`; a note-sorting request goes to `other:triage`;
- `bootstrap`: L4, from vanilla through `customize-harness` to a fixture task.

Format: [../README.md](../README.md). Example: [happy-path.yaml](happy-path.yaml).
