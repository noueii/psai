---
name: customize-harness
description: "Builds and changes the owner's psai setup WITH the owner, in the stack they pick (their overlay, a stack they author, or a new one): bootstraps a first workflow by interviewing them, or adds or changes one piece (workflow, routing, step, role, guide, template, owner rule, skill). Use when `work` finds no matching workflow and the owner agrees to set one up, when the owner wants to change how agents work or add, adopt or change a skill, or when a proposed-rule from an inbox is accepted."
---

# customize-harness

Run `psai` as the nudge says if it isn't on PATH. Everything you write is filed per LAYOUT.md (`psai resolve file psai:LAYOUT.md`), and ONLY in places LAYOUT marks as the owner's. Never edit upstream-owned files (skills, scripts, install.sh, evals except new scenarios, LAYOUT.md, folder READMEs, docs, instructions/global.md), so upstream updates merge cleanly. **Stage, never publish:** edit and validate in the stage worktree `S` of the repo you change (`psai stage` for your overlay, `psai stage <stack>` for a stack you author), never in the live setup, which sessions read. Make no branch, commit or PR: the retro at the end of the task (or a `sync` node) carries everything, one PR per repo, which the owner merges.

## How to ask
Ask the owner ONE question per message, with the fixed block, kind `question`, node `customize` (`psai resolve file psai:skills/work/escalation.md`). Offer options with your recommendation first. Don't ask what the owner already told you or what LAYOUT.md settles.

## First: which stack does this change?
Ask it first, unless the owner already said. Options (`psai stack list` shows what's installed):
- **your overlay (`nostack`)**: your own workflows and your adjustments to other people's stacks. Recommend it for personal work;
- **a stack you author** (one `psai stack list` shows as `dev`);
- **a new stack** to share or publish: run `psai new-stack <name>`, which creates it and adds it as a dev stack.

A pinned stack someone else authors is never edited: its files change through an override in your overlay (below), and the retro can draft a suggestion for its author. Then work in that stack's stage worktree `S` (`psai stage <stack>`, or `psai stage` for your overlay) and validate with `psai check S`.

## Bootstrap (no workflows yet)
1. **Interview** the owner about how they work, one question at a time. Cover EVERY topic below before proposing anything; skip a topic only if the owner already answered it:
   - what kinds of tasks they hand to agents;
   - the steps a task goes through, and where a human must look;
   - which roles exist and what each may change;
   - which checks prove the work is right;
   - when agents may decide alone and when they must ask;
   - what the final report of a task contains.
2. **Offer the design patterns** in [patterns/](patterns/) as options, one at a time and only where they fit. Never add one the owner didn't choose:
   - [separate roles](patterns/separate-roles.md)
   - [a checker that works from the spec](patterns/checker-from-spec.md)
   - [change limits enforced by diff](patterns/diff-limits.md)
   - [loop limits](patterns/loop-limits.md)
   - [sizing](patterns/sizing.md)
   - [a final report template](patterns/handover.md)
   - [a decide-and-log escalation policy](patterns/decide-and-log.md)
   - [end the workflow with retro, then sync](patterns/retro-sync-tail.md)
3. **Propose** the first workflow as a short summary: nodes, edges, roles and what each may change, human points, loop limits, attachments, rules for every task. Ask for acceptance; if the owner adds or corrects something, revise and ask again. Then build it (below).

## Add or change one piece
1. Ask what should change and why, if that isn't clear yet.
2. Ask the scope: everywhere, or this workflow only. A rule for one repo only belongs in that repo's own AGENTS.md or docs, not in psai: offer to write it there instead.
3. Pick the place and format from LAYOUT.md. To change a file of an installed stack (`stack:path`), never edit the stack: run `psai stack override <stack>:<path> --in S`, which copies it to `S/overrides/<stack>/<path>`, and edit that copy. It wins by name, and `psai stack update` reports when the original changes. Validate it with `psai stack check <stack>`.

## Skills for a role or step
Name them in the file's frontmatter, `skills: {required: [...], optional: [...]}`. For each one:
1. Run `psai skills` (the live registry). Installed anywhere: just reference it by name.
2. Someone else's: add a pinned entry to `skills.yaml` (a tag or commit, never a branch; format in `psai resolve file my-skills/README.md`).
3. Doesn't exist: write it with the owner in `my-skills/<name>/SKILL.md`, one question at a time.
4. Only for one repo: `<repo>/.agents/skills/<name>/`, linked from `<repo>/.claude/skills/<name>`, and listed as optional.

Unmanaged skills (`psai skills --unmanaged`): offer to adopt one with `psai adopt <name>` (it moves the skill into your overlay's `my-skills/` or `skills.yaml`, which the retro's PR carries; `--to <stack>` adopts it into a stack you author instead). Then run `psai check`.

## Build
1. In the stage worktree, write the files per LAYOUT.md, using the formats in each folder's README.md. For a role, also create `knowledge/roles/<role>/INDEX.md` and `inbox.md`.
2. Rules for every task (for example an escalation policy) go in `instructions/owner.md`. Every tool's plugin picks it up live.
3. For a new workflow, also write:
   - its branch in `workflows/ROUTING.yaml` (create the file for the first workflow);
   - its simulator cases `workflows/<name>.cases.yaml`, covering every edge you added, every loop limit and every escalation;
   - at least one eval scenario `evals/scenarios/<name>.yaml`.
4. Validate the stage worktree `S`:
   - `psai check S`;
   - `psai simulate S`;
   - `psai graph S --update-readme`, which writes `workflows/GRAPHS.md`.

   Fix until all three pass.
5. Leave it staged: no branch, commit or PR. Report what you staged, where, and how to try it; the retro's PR (or sync's) delivers it.
