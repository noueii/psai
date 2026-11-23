---
name: sync
description: "Brings this machine in step: fast-forwards your stack's clone, updates psai and the installed stacks through each tool's own install channel, and opens one PR with everything staged. Use when a workflow reaches a sync node, or when the owner asks to sync or update psai."
---

# sync

Sync runs only here: at a `sync` node, or when the owner asks. Nothing else updates psai. `S` is your stack and `T` its stage (the `work` skill's `your-stack.md`).

1. **Your stack:** `git -C "$S" fetch -q origin` (skip it when there's no `origin`). When `git -C "$S" status -sb` says behind, `git -C "$S" pull --ff-only` (your uncommitted inbox entries stay). It can't fast-forward: change nothing, and put "sync waiting: needs you" with the reason in the final report. Never merge, rebase or reset yourself.
2. **psai and the stacks you installed:** update them with the channel each came from, for the tool you run in. Run only the ones that apply:
   - Claude Code plugin: `claude plugin marketplace update <marketplace>` then `claude plugin update <plugin>@<marketplace>`, for psai and each stack's plugin;
   - pi: `pi update --extensions`; omp: `omp plugin upgrade`;
   - `npx skills`: `npx skills update`;
   - a clone linked with `scripts/link-skills.sh`: `git -C <clone> pull --ff-only`.

   A command fails or isn't there: skip it and note it. The tool may need a restart to load new skills: say so.
3. **PR:** finish the stage as `your-stack.md` says, with a short summary of steps 1-2 plus any retro report waiting in it as the PR body.
4. **Report:** your stack (up to date, fast-forwarded from..to, or waiting), what each channel updated, the PR (or "no PR").
