# evals/fixtures/

Inputs for tests, never installed.
- [textkit/](textkit/README.md): a tiny Python repo with its own tests. Each eval run works on a throwaway copy.
- [sync-tail/](sync-tail/README.md): an overlay on harness-content whose `example` workflow ends `report → retro → sync → ready`.
- [stacks/](stacks/README.md): neutral test stacks (`other`, the overlay `nostack`) for multi-stack checks; `harness-content` is the stack `example`.
- [model-tier/](model-tier/README.md): an overlay on harness-content where the `checker` has `model: fast`.
- [harness-content/](harness-content/README.md): neutral TEST harness content (a tiny `example` workflow), overlaid on a vanilla harness copy for L0, L2 and L3.

A new fixture repo is a folder with its own README and checks. A new content fixture mirrors the harness root and follows LAYOUT.md.
