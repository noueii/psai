# evals/fixtures/sync-tail/

An overlay on the [example](../stacks/example/README.md) test stack: the same `example` workflow, ending `report → retro → sync → ready`. The `retro-sync` eval scenario uses both (`stacks: { example: [stacks/example, sync-tail] }`); `scripts/check.sh` validates and simulates the combination.
