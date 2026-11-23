---
name: retro
description: "Reviews a finished task: reads the run (trace, inbox entries, escalations, loops at their limit, rejected diffs, review findings, time and cost), ranks findings by severity, stages changes to your stack and opens one PR for you to merge, or drafts a suggestion for another stack's author. Use when a workflow ends (work runs it, or a retro node), or when a task outside a workflow is done and something was captured or staged."
---

# retro

You only look back and stage. Never edit a live repo (except inboxes in your stack), other repos, or GitHub directly. `S` is your stack and `T` its stage (the `work` skill's `your-stack.md`).

1. **Gather:**
   - the trace: `cat "${PSAI_TRACE:-$(git rev-parse --absolute-git-dir)/psai-trace}"` in the task's repo (nodes, check-diff results);
   - new inbox entries: `git -C "$S" diff -- knowledge`, plus untracked inboxes (`git -C "$S" status --short knowledge`);
   - what is already staged: `git -C "$T" status --short`, when `T` exists;
   - what the conversation shows: escalations, review comments, owner corrections, retries, slow or costly stretches.
2. **Look for** (each finding names its evidence):
   - **navigation:** files or facts agents hunted for; **information access:** docs, tools or credentials that were missing;
   - **automated checks:** a mistake a script could have caught; **standards:** a mechanical rule becomes a check, a judgement call becomes a guide;
   - **always-loaded text** that is too big or full of no-ops; **tool economy:** wasted or repeated calls;
   - **workflow shape:** loops at their limit, nodes never used, escalations that should have been decisions; **roles missing skills**;
   - **knowledge worth keeping** (inbox entries to promote).
3. **Rank** findings high / medium / low and keep the ones that change future work.
4. **File each finding:**
   1. about the project: the final report only;
   2. your preference or environment (an owner correction, a tool, a path, a credential gap), or a workflow from your own stack: stage it in your stack;
   3. a workflow, role or guide from someone else's stack: your copy is read-only. Draft a suggestion for its author (what, why, evidence) in the final report. To get the change now, offer to copy that workflow into your stack under your own name (`customize-harness`). Open an issue or PR on their repo only after the owner says yes to a fixed block, kind `question`;
   4. psai itself: a suggestion in the final report, as 3.
5. **Stage** in `T`, filed per the `customize-harness` skill's `LAYOUT.md`, in its formats: promoted knowledge (`knowledge/facts/`, `knowledge/decisions/`, `knowledge/INDEX.md`; then delete the promoted entries from the inbox in `S`), and guide, role, step, workflow or rules changes.
6. **Write the report** to a temp file: `# Retro: <task>`, then `## Findings` (ranked: `1. [high] <category>: <finding>. Evidence: ... Change: ...`), `## Staged`, `## For the project`.
7. **Finish** as `your-stack.md` says, with the report as the PR body, unless a `sync` node follows in this workflow: then sync finishes. Nothing staged: no PR.
8. Put the ranked findings, the PR (or "no PR") and any drafted suggestion in your final report under `## Retro`.
