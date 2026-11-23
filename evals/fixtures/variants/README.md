# evals/fixtures/variants/

Folders copied over the `example` test stack for one scenario (`stacks: { example: [stacks/example, variants/<name>] }`); `scripts/check.sh` checks each result.
- `model-tier/`: the shared checker has `model: fast`.
- `sync-tail/`: `workflow-example-change` ends `report → retro → sync → ready`.
