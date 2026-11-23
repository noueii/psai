# evals/fixtures/stacks/

Neutral TEST stacks, never installed for real: `scripts/check.sh` checks them and the eval driver loads them as plugins.
- [example/](example/README.md): `workflow-example-change`, a tiny workflow that exercises every feature, plus `example-shared` (a shared role, guide and template) and `example-change-notes` (a skill a role requires).
- [other/](other/README.md): `workflow-other-triage` (a `skill:path` read into `example-shared`, a handoff to `workflow-example-change`) and always-on rules in `other-rules`.
