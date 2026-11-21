---
name: retro
description: "Reviews a finished task: reads the run (trace, inbox entries, escalations, loops at their limit, rejected diffs, review findings, time and cost), ranks findings by severity, and stages ONE PR on the owner's fork with everything worth keeping. Use when a workflow ends (work runs it, or a `retro` node), when a task outside a workflow is done and something was captured or staged, or when the nudge says earlier sessions ended without one."
---

# retro

`H` is the harness root (`$PSAI_HOME` or `~/.psai`). Run `psai` as `python3 H/scripts/psai.py` if it isn't on PATH. You only look back and stage: never edit the live `H` (except inboxes), other repos, or GitHub directly.

1. **Gather:** `psai retro gather`. Add what the conversation shows: review comments, owner corrections, retries, slow or costly stretches.
2. **Look for** (each finding names its evidence):
   - **navigation:** files or facts agents hunted for; **information access:** docs, tools or credentials that were missing;
   - **automated checks:** a mistake a script could have caught; **standards:** a mechanical rule becomes a check, a judgement call becomes a guide;
   - **always-loaded text** that is too big or full of no-ops; **tool economy:** wasted or repeated calls;
   - **workflow shape:** loops at their limit, nodes never used, escalations that should have been decisions; **roles missing skills**;
   - **knowledge worth keeping** (inbox entries to promote); **drift** between the tools and psai.
3. **Rank** findings high / medium / low and keep the ones that change future work.
4. **Stage** the changes in the stage worktree (`psai sync stage` prints it), filed per `H/LAYOUT.md`, user-owned paths only, using customize-harness's formats: promoted knowledge (`knowledge/facts/`, `knowledge/decisions/`, `INDEX.md`), guide, role, step or check changes. Validate there (`scripts/check.sh --quick`). Findings about the project itself go in the final report, not here.
5. **Write the report** to a temp file: `# Retro: <task>`, then `## Findings` (ranked: `1. [high] <category>: <finding>. Evidence: ... Change: ...`), `## Staged`, `## For the project`.
6. **Finish:** `psai retro finish --report <file>` (add `--pending` when covering earlier sessions). It builds the one PR branch (the report is its description) and pushes it to the fork, unless a `sync` node follows in this workflow: then sync carries it. Nothing staged or captured: no PR.
7. Put the ranked findings and the branch (or "no PR") in your final report under `## Retro`.
