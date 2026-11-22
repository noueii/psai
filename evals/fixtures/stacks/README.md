# evals/fixtures/stacks/

Neutral TEST stacks for multi-stack checks (ADR 0011), never installed. `check.sh` builds a temp `PSAI_HOME` in the stacks layout from them: `framework/` links the psai clone, `stacks/example/` is [../harness-content/](../harness-content/README.md) (it has a `stack.yaml`), `stacks/other/` and `overlay/` are copied from here.
- [other/](other/stack.yaml): a second stack: a `triage` workflow, always-on rules (`instructions/stack.md`), a cross-stack `read:` of `example:guides/example-rules.md`, a private (unexported) guide, and its own `change-notes` skill, which collides with example's.
- [nostack/](nostack/stack.yaml): the overlay: `stacks.yaml` (example, other), an override of `example:guides/example-rules.md`, additive knowledge for example's `doer`, its own skill `mine` and owner rules.

A new fixture stack is a folder with a `stack.yaml` (schemas/stack.schema.json) and the content folders per LAYOUT.md.
