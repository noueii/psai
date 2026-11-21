---
name: sync
description: "Brings this machine in step with the owner's psai fork: a deterministic out-of-sync check first (free when nothing changed), then a fast-forward-only update with re-install and migrations, adoption of tool drift by staging, and ONE PR for this machine with everything staged or captured. Use when a workflow reaches a `sync` node, or when the owner asks to sync or update psai."
---

# sync

`H` is the harness root (`$PSAI_HOME` or `~/.psai`). Run `psai` as `python3 H/scripts/psai.py` if it isn't on PATH. Sync runs only here: when a workflow has a `sync` node or the owner asks. Nothing else updates psai.

1. **Check:** `psai sync check`. "in sync" means you're done: say so in one line and move on.
2. **Update:** `psai sync update` when it reports `behind`, `install` or `migrations`. It fast-forwards only, keeps local inbox entries, re-installs and runs pending migrations. Exit 4, a conflict, changed nothing: stop and put "psai update waiting: needs you" with its reason in the final report. Never merge, rebase or reset `H` yourself.
3. **Drift:** `psai sync drift` lists what changed in the tools since the last scan. Adopt only what's worth keeping, by staging it:
   - a new unmanaged skill: `psai adopt <name>`, or add it to `skills.yaml`'s `ignore:` in the stage worktree;
   - a rule in a global instruction file (CLAUDE.md, AGENTS.md): a proposed owner rule in `instructions/owner.md` in the stage worktree (`psai sync stage`);
   - a durable fact in Claude's memory: an inbox entry (capture-knowledge).
4. **One PR:** `psai sync pr --body-file <file>`, with a short summary of steps 1-3. It builds branch `psai/sync-<host>-<date>` in a separate worktree with everything staged or captured, including waiting retro reports, pushes it to the fork and opens the PR. The live `H` is only ever fast-forwarded.
5. Report: in sync, updated (from..to), the PR branch, or "psai update waiting: needs you".
