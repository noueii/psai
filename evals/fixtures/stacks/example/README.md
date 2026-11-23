# example (test stack)

A neutral TEST stack in psai 4's layout, never installed for real: the eval driver loads it as a plugin (`--plugin-dir`), and `scripts/check.sh` checks it. `workflow-example-change` exercises every feature: a role inside the workflow (`roles/doer.md`, which requires `example-change-notes`), a shared role (`example-shared:roles/checker.md`, may change nothing), `skill:path` reads, a human node, a limited loop, an escalation. Example: [skills/workflow-example-change/workflow.yaml](skills/workflow-example-change/workflow.yaml).
