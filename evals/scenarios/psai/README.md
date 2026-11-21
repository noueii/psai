# evals/scenarios/psai/

psai's own scenarios (upstream-owned). They run on neutral test content and never encode anyone's setup:
- `vanilla-no-workflow`: a task on vanilla escalates and offers `customize-harness`;
- `happy-path`, `ambiguous`, `boundary`: L3, on `evals/fixtures/harness-content/`;
- `routes-unnamed`, `quick-question`, `repeatable-unmatched`: L3 routing (a match the request doesn't name, a one-off, a repeatable task with no workflow);
- `role-skill`, `missing-skill`: L3 role skills (the doer requires `change-notes`: it is listed in the brief and used; when it is missing, work escalates from `do` offering to install it);
- `bootstrap`: L4, from vanilla through `customize-harness` to a fixture task.

Format: [../README.md](../README.md). Example: [happy-path.yaml](happy-path.yaml).
