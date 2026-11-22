---
name: sync
description: "Brings this machine in step: a deterministic out-of-sync check first (free when nothing changed), then fast-forward-only updates of your overlay and the psai framework with re-install and migrations, newer stack releases to review, adoption of tool drift by staging, and one PR per target repo with everything staged or captured. Use when a workflow reaches a `sync` node, or when the owner asks to sync or update psai."
---

# sync

Run `psai` as the nudge says if it isn't on PATH. Sync runs only here: when a workflow has a `sync` node or the owner asks. Nothing else updates psai.

1. **Check:** `psai sync check`. "in sync" means you're done: say so in one line and move on. It reports: a newer framework release, a pinned stack with a newer release in range, new commits on your overlay's remote, an install or migrations behind, sessions or staged changes not yet in a PR, and tool drift.
2. **Update:** `psai sync update` for `behind`, `framework`, `install` or `migrations`. It fast-forwards your overlay (keeping local inbox entries) and the framework, then re-installs. Exit 4 changed nothing: stop and put "psai update waiting: needs you" with its reason in the final report (a conflict, or a framework release an installed stack doesn't support yet). Never merge, rebase or reset anything yourself, and never pass `--force` without the owner's yes.
3. **Stacks:** for each `stack` line, `psai stack update <name>` moves its pin; report any override whose original changed (`psai stack diff <name> <path>`). Never merge an override yourself.
4. **Drift:** `psai sync drift` lists what changed in the tools since the last scan. Adopt only what's worth keeping, by staging it in your overlay (`psai stage`):
   - a new unmanaged skill: `psai adopt <name>`, or add it to `skills.yaml`'s `ignore:`;
   - a rule in a global instruction file (CLAUDE.md, AGENTS.md): a proposed owner rule in `instructions/owner.md`;
   - a durable fact in Claude's memory: an inbox entry (capture-knowledge).
5. **PRs:** `psai sync pr --body-file <file>`, with a short summary of steps 1-4. It builds one branch per target repo with changes (your overlay, each stack you author), including waiting retro reports, pushes it where there's a remote and opens the PR. Live repos are only ever fast-forwarded.
6. Report: in sync, updated (from..to), stacks updated, the PR branches, or "psai update waiting: needs you".
