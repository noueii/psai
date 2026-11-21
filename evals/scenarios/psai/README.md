# evals/scenarios/psai/

psai's own scenarios (upstream-owned). They run on neutral test content and never encode anyone's setup:
- `vanilla-no-workflow`: a task on vanilla escalates and offers `customize-harness`;
- `happy-path`, `ambiguous`, `boundary`: L3, on `evals/fixtures/harness-content/`;
- `bootstrap`: L4, from vanilla through `customize-harness` to a fixture task.

Format: [../README.md](../README.md). Example: [happy-path.yaml](happy-path.yaml).
