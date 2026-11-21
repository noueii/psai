# End the workflow with retro, then sync

**What:** the last nodes before `ready` are `retro`, then `sync`: `handover → retro → sync → ready`, as `retro: { skill: retro, next: [{ to: sync }] }` and `sync: { skill: sync, next: [{ to: ready }] }`.
**Why:** the retro stages what the task taught; sync then fast-forwards this machine and opens ONE PR with everything. Without a `sync` node, psai updates only when the owner asks an agent to sync (work runs a retro after every workflow anyway; the node only fixes its place).
**How:** offer it once the main nodes are agreed; never add it unasked.
