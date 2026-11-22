# evals/fixtures/

Inputs for tests, never installed.
- [textkit/](textkit/README.md): a tiny Python repo with its own tests. Each eval run works on a throwaway copy.
- [stacks/](stacks/README.md): neutral test stacks: `example` (one tiny workflow that exercises every feature), `other`, and the overlay `nostack`. The tests and the L3 evals install them in temp homes.
- [sync-tail/](sync-tail/README.md): an overlay on the `example` stack whose `example` workflow ends `report → retro → sync → ready`.
- [model-tier/](model-tier/README.md): an overlay on the `example` stack where the `checker` has `model: fast`.

A new fixture repo is a folder with its own README and checks. A new test stack follows LAYOUT.md's "inside a stack" and has a `stack.yaml`.
