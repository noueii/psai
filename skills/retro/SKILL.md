---
name: retro
description: "Reviews a finished task: reads the run (trace, inbox entries, escalations, loops at their limit, rejected diffs, review findings, time and cost), ranks findings by severity, files each where it belongs (your overlay, a stack you author, or a suggestion for another stack's author) and stages one PR per target repo. Use when a workflow ends (work runs it, or a `retro` node), when a task outside a workflow is done and something was captured or staged, or when the nudge says earlier sessions ended without one."
---

# retro

Run `psai` as the nudge says if it isn't on PATH. You only look back and stage: never edit a live repo (except inboxes), other repos, or GitHub directly.

1. **Gather:** `psai retro gather`. Add what the conversation shows: review comments, owner corrections, retries, slow or costly stretches.
2. **Look for** (each finding names its evidence):
   - **navigation:** files or facts agents hunted for; **information access:** docs, tools or credentials that were missing;
   - **automated checks:** a mistake a script could have caught; **standards:** a mechanical rule becomes a check, a judgement call becomes a guide;
   - **always-loaded text** that is too big or full of no-ops; **tool economy:** wasted or repeated calls;
   - **workflow shape:** loops at their limit, nodes never used, escalations that should have been decisions; **roles missing skills**;
   - **knowledge worth keeping** (inbox entries to promote); **drift** between the tools and psai.
3. **Rank** findings high / medium / low and keep the ones that change future work.
4. **File each finding** (gather lists the targets):
   1. about the project: the final report only;
   2. your preference or environment (an owner correction, a tool, a path, a credential gap): your overlay, as knowledge, an owner rule (`instructions/owner.md`) or an override;
   3. a stack's content (its workflow shape, a role missing a skill, a guide wrong for everyone), and you author it (`dev`): stage it in that stack (`psai stage <stack>`);
   4. the same, in someone else's pinned stack: an override in your overlay (`psai stack override <stack>:<path> --in "$(psai stage)"`), so you get it now, plus `psai retro suggest <stack> --note "<why>"`, which drafts a suggestion for its author. Never open that PR yourself: ask the owner with the fixed block, kind `question`, and only on a yes run `psai retro suggest <stack> --open`;
   5. the framework (psai itself): a suggestion in the final report, as 4.
5. **Stage** in the target's stage worktree (`psai stage [<stack>]`; your overlay by default), filed per LAYOUT.md (`psai resolve file psai:LAYOUT.md`), using customize-harness's formats: promoted knowledge (`knowledge/facts/`, `knowledge/decisions/`, `INDEX.md`), guide, role, step or check changes. Validate (`psai check --quick <stage>`, or `psai stack check <stack>` for a stack).
6. **Write the report** to a temp file: `# Retro: <task>`, then `## Findings` (ranked: `1. [high] <category>: <finding>. Evidence: ... Change: ...`), `## Staged`, `## For the project`.
7. **Finish:** `psai retro finish --report <file>` (add `--pending` when covering earlier sessions). It builds one branch per target repo with changes (the report is each description) and pushes it where the target has a remote, unless a `sync` node follows in this workflow: then sync carries them. Nothing staged or captured: no PR.
8. Put the ranked findings, the branches (or "no PR") and any drafted suggestion in your final report under `## Retro`.
