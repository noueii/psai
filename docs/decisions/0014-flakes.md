# 0014: flakes (2026-11-23)

Status: **proposed**, the plan only. Nothing here is built. The owner agreed the structure (below), and this ADR plans how to build it. The owner decides the open questions in §12. Once accepted, it supersedes [0013](https://github.com/noueii/psai/blob/plan-one-skill/docs/decisions/0013-one-stack-one-skill.md) (never merged), and most of [0012](0012-skills-only.md) (§10).

## Decision (the owner's)
A **flake** is a bot: one purpose, with what it needs. A user's flakes live in one git repo, and **the repo's root folder is the only skill** installed into their tools.

```
flakes/                     the user's repo (a copy of psai); the root is the one skill
  SKILL.md                  the router: the ONLY SKILL.md. Broad, model-invoked. Picks a flake and hands over
  skills/                   shared internal skills, one folder each, entry file ENTRY.md (never SKILL.md)
    memory/                 MANDATORY for every flake
    rsi/                    MANDATORY for every flake (recursive self-improvement)
    escalate/               optional: when and how to ask the owner; the report format
    handoff/                optional: call another flake as a sub-agent, or pass the task to it
    new-flake/              builds or changes flakes with the owner, one question at a time
  docs/                     the owner's rules and reference for every flake, with INDEX.md
  MEMORY.md  memory/        shared memory, in Orca's format
  flakes/
    <name>/
      FLAKE.md              who this bot is (frontmatter + plain prose)
      workflow.md           OPTIONAL, free-form: the procedure in the owner's own words
      skills/<s>/ENTRY.md   the flake's own bundled skills
      docs/                 the flake's own docs, with INDEX.md (they override root docs)
      MEMORY.md  memory/    the flake's own memory, including memory/runs.md
```

- **No roles anywhere.** A planner, a coder, a QA or a reviewer is just another flake. A "workflow" is a flake (say `task-manager`) whose FLAKE.md, or an optional free-form `workflow.md`, says in the owner's words which flakes it calls and in what order. psai enforces no workflow format: `new-flake` offers guidance and a short example, never a schema.
- **No SKILL.md below the root.** Internal skills use `ENTRY.md` (§2.1).
- **Install:** symlink the root into `~/.claude/skills` and `~/.agents/skills`. **Update:** `git pull`. Optionally, add one line to each tool's global instructions.
- **No** per-tool plugins, manifests, hooks, extensions, custom CLI, runtime or AI evals. CI runs deterministic, structural checks only.
- **Hard guarantees only where they are cheap:** escalate's fixed block (built by a script), and an optional `may_change` diff check when one flake calls another (§12, Q3).
- **RSI tiers:** memory is written directly. Flake behaviour (`flakes/**`, `docs/**`) is staged and becomes ONE PR per task. The root (`SKILL.md`, `skills/*`) gets its own PR.
- **Orca:** an Orca bot can host a flake. Its SOUL.md says "you are flake `<name>`". FLAKE.md ≈ SOUL.md and MEMORY.md ≈ MEMORY.md, on purpose.
- **Work and personal are separate WSL distros**, so there is one flakes repo per environment.
- **psai becomes the vanilla base:** the router, the shared skills, empty `docs/`, `memory/` and `flakes/`, a spec, a CI validator and a human guide. A user's repo starts as a clone of it and merges psai's updates to the root files.
- **Source:** the owner's brief for psai 5 (task_fc11de8ffe78, 2026-11-23), revised three times during planning: docs indexes; workflows optional; workflows composed of flakes, with no roles and no enforced format.

**Why:** 4.0 shipped six top-level skills and five packaging channels. Its naming rules (`workflow-<stack>-*`, `<stack>-rules`) exist only because tools merge skills into one flat list. It also shipped a YAML state machine with a trace script and a simulator: machinery to maintain that the owner does not want. With one root skill, nothing internal can collide, and every tool already discovers it. With flakes calling flakes, one concept (a bot with a purpose, docs and memory that improves itself) replaces workflows, roles, guides, templates and knowledge layers.

**Compared with pstack** (`cursor/plugins/pstack`, read 2026-11-23). Its `poteto-mode` routes each task to one of 22 playbooks and runs sibling skills by path. We keep the shape (one entry routes, everything else is loaded by path) and change three things:
- pstack's 39 skills are each discovered on their own; ours are invisible behind one root.
- `poteto-mode` is manual (`disable-model-invocation`); our router is model-invoked.
- pstack's playbooks are fixed prose written by one author; our flakes are the owner's, and each rewrites itself from evidence (rsi).

---

## 1. Discovery per tool (verified 2026-11-23, from 0013 §2)
| | Claude Code 2.1.330 | opencode 1.18.30 | pi 0.80.2 / 1.6.0 | omp 18.11 / 19.1 |
|---|---|---|---|---|
| user skill dirs | `~/.claude/skills/` | `~/.config/opencode/skill(s)/`, `~/.claude/skills/`, `~/.agents/skills/` | `~/.pi/agent/skills/`, `~/.agents/skills/` | `~/.omp/agent/skills/`, `~/.agents/skills/`, `~/.claude/skills/` |
| depth | `<dir>/<name>/SKILL.md` | **recursive** `skills/**/SKILL.md`, follows symlinks, includes dot folders | recursive, but **stops at the first folder with a SKILL.md** | **one level** |
| a nested SKILL.md in our folder | ignored (to be proven, §9.2) | **registered as another skill** | ignored | ignored |
| description limit | listing truncates at 1536 characters | none found | 1024 (warns) | none found |
| symlinked folder | yes | yes | yes, deduped by real path | yes, deduped by real path |
| global instructions file | `~/.claude/CLAUDE.md` | `~/.config/opencode/AGENTS.md` | `~/.pi/agent/AGENTS.md` | `~/.omp/agent/AGENTS.md` |

So exactly one `SKILL.md` per installed folder is required, not just tidy.

## 2. The spec (`spec/SPEC.md`, flakes format 1.0)

### 2.1 Fixed names and why
- **`SKILL.md` only at the root.** opencode registers any nested `SKILL.md` as another skill. On a case-insensitive filesystem (Windows drives under `/mnt/c`, macOS), `skill.md` *is* `SKILL.md`, so the ban covers every casing. The validator matches names case-insensitively.
- **Upper-case names are files the machinery reads by name:** `SKILL.md`, `ENTRY.md`, `FLAKE.md`, `MEMORY.md`, `INDEX.md`. Lower-case names are content (`docs/testing.md`, `memory/runs.md`, `workflow.md`). That is why the docs index is **`INDEX.md`**, matching `MEMORY.md` (the owner asked for one name, chosen and applied consistently).
- **No `.git`, worktree or clone below the root** other than the root's own `.git`: opencode scans dot folders, and a staged copy would carry a second `SKILL.md`. That's why staging happens outside the repo (§4.5).
- **Every path in the repo is relative to the root**, except inside an `ENTRY.md`, where paths are relative to that skill's folder. The router says once: "paths are relative to the folder this SKILL.md is in." Every tool tells the model that folder: Claude Code and opencode print a "Base directory for this skill" line, and pi and omp give the path of the `SKILL.md` they read. A symlink resolves to the clone, so `git -C <root>` works.

### 2.2 Root `SKILL.md` (the router)
```yaml
---
name: flakes
description: "Your bots for software work. Routes every task (feature, fix, refactor, review, docs, chores, questions about code) to the bot that fits, with its rules and memory, or handles a one-off directly. Use when starting any software task, before acting on it."
metadata:
  flakes-format: "1.0"
  version: "5.0.0"
---
```
- Use the Agent Skills fields only, and never `disable-model-invocation`.
- `name` is fixed: `flakes` in every copy, so psai's updates never conflict on it (§12, Q2).
- The description is at most 1024 characters (aim for 400) and contains "Use when".

The body is at most 600 words, in these sections:
1. **Called flakes.** "If your prompt says you were called as flake `<x>` (by `handoff`), do not route: follow `flakes/<x>/FLAKE.md` as §3 says and return." This replaces 4.0's `PSAI_ROLE` and the last line of the nudge.
2. **Read first:** `docs/INDEX.md` (the owner's rules for every task) and `flakes/INDEX.md`.
3. **Route** (§2.6). The output is one of: hand over to one flake; handle a one-off; offer `new-flake`; or escalate a tie.
4. **Hand over:** the fixed sequence in §3.
5. **One-off:** handle it directly under the root docs, then append a line to `memory/unrouted.md` (§2.5) unless the task was a plain question.
6. **Changes to this repo** are only made through `new-flake` or `rsi`, never by hand-editing the live clone (memory excepted).

### 2.3 `flakes/<name>/FLAKE.md`
```yaml
---
name: reviewer                       # = folder name: lowercase, digits, single hyphens, ≤ 64 characters
when: "Reviewing a pull request or diff for correctness and style before merge."   # ≤ 200 characters; the router matches on it
group: code                          # optional; used once there are more than 20 flakes (§2.6)
skills:                              # optional; memory and rsi are implicit and never listed
  required: [escalate, installed:gh-pr-review]
  optional: [handoff, lint-rules]
calls: [coder]                       # optional: flakes it may call or pass to (needs handoff)
may_change: nothing                  # optional: anything | tests | nothing; checked when it is CALLED (Q3)
autonomy: stop-and-record            # required when escalate is not in skills: decide-and-record | stop-and-record
---
You are the reviewer. <purpose in one sentence>.
<What you do, in the owner's words: free prose, or "Follow workflow.md".>
Done when: <...>.
Never: <...>.
```
- **Skill names:**
  - a bare name is a shared skill (`skills/<s>/ENTRY.md`) or this flake's bundled skill (`flakes/<name>/skills/<s>/ENTRY.md`). The validator rejects a bundled name that shadows a shared one.
  - `installed:<s>` is a skill the tool discovers itself (third-party, installed through its own channel, e.g. mattpocock's `tdd`).
- **Loading:**
  - Bundled and shared skills: read their `ENTRY.md` when FLAKE.md, `workflow.md` or a doc says to use them. Required ones are read at hand-over.
  - An installed skill: load it the way the tool loads skills (Claude Code's Skill tool, opencode's `skill` tool, pi and omp read its `SKILL.md`).
  - A missing **required** skill stops the flake before it starts: escalate, or record it under the autonomy fallback. A missing optional one is noted in the report.
- **Vendoring** a third-party skill means copying it into `flakes/<name>/skills/<s>/` (or the root `skills/` for every flake), renaming `SKILL.md` to `ENTRY.md`, and keeping its `LICENSE`. Its `ENTRY.md` gains `metadata: {source: github:owner/repo/path, commit: <sha>}`. Links of the form `../<x>/SKILL.md` (pstack style) are rewritten. `new-flake` does this, and the validator's link check catches any it missed.
- **`workflow.md`** is optional and free-form. If it exists, FLAKE.md links to it. The validator only checks that the link resolves, and that every flake it names in backticks as `flake:<name>` exists and is in `calls`.

### 2.4 `ENTRY.md` (internal skills)
```yaml
---
name: memory                         # = folder name
description: "What it does. Use when ..."   # same rules as a SKILL.md description, ≤ 1024 characters
metadata: { flakes-format: "1.0" }   # shared skills; vendored ones add source and commit
---
```
The body is at most 800 words. Supporting files sit beside it and are loaded by path from it.

### 2.5 Memory, runs and docs formats
**`MEMORY.md`** (root and per flake), the same format as Orca's bot memory:
```md
# Memory

One line per fact, newest first. Longer notes go in memory/<topic>.md.
- 2026-11-23 The api repo's tests need `make db` first. Details in memory/api.md. · from: coder
```
- Each line is `- YYYY-MM-DD <fact>` with an optional ` · from: <flake>`.
- A fact is **descriptive** (what is true). A rule ("always X") is not memory: it goes to `docs/` through a PR (§4).
- A topic file `memory/<topic>.md` is free prose, linked from at least one MEMORY.md line.
- `memory/archive.md` holds retired lines, marked `~~old fact~~ · replaced YYYY-MM-DD` or `· moved YYYY-MM-DD` (Orca's convention).

**`flakes/<name>/memory/runs.md`**: one line per run, oldest first, appended at the end:
```
- 2026-11-23 14:05 | fix-login-redirect | done | repo=noueii/app calls=coder,reviewer esc=0 fixes=1 skipped=- | owner corrected the redirect target
- 2026-11-24 09:12 | retro | 6 runs | pr=https://github.com/you/flakes/pull/12 root-pr=-
```
- Fields, separated by ` | `:
  1. date and time;
  2. task slug;
  3. outcome: `done`, `escalated`, `stopped`, `decided`, `passed` (handed over) or `failed`;
  4. tags (`key=value`, spaces between): `repo`, `calls`, `esc` (escalations), `fixes` (owner corrections), `viol` (may_change violations), `loops` (retries in the owner's own loops), `skipped` (missing optional skills), `caller`;
  5. a note of at most 140 characters.
- A `retro` line marks a retrospective. The runs after it are what the next retro reads.

**`memory/unrouted.md`** (root) uses the same line shape for one-off tasks: `- <date> | <slug> | one-off | repo=... | why no flake fit`. It is the evidence base for proposing new flakes.

**`docs/INDEX.md`** (root, and per flake in `flakes/<name>/docs/INDEX.md`):
```md
# Docs

- [testing.md](testing.md): read when writing or changing tests.
- [release.md](release.md): read when tagging or publishing a release.
```
- Each line is `- [<file>](<file>): read when <condition>.` and is at most 160 characters.
- `docs/` is flat (no subfolders), and every other `.md` in it is listed exactly once.
- Agents read only INDEX.md up front, and open a doc when its "read when" fits.
- **A flake's docs override the root's:** both indexes are read, a flake doc with the same file name replaces the root one, and on a clash in content the flake's text wins.
- **Who updates it:** `new-flake` and `rsi` update the index in the same staged change that adds, renames or removes a doc. The validator enforces it both ways (§9.1).

### 2.6 How the router lists and picks flakes
- **`flakes/INDEX.md`** mirrors the frontmatter: one line per flake, `- <name>: <when>`, with `when` copied exactly from FLAKE.md. The router reads this ONE file instead of N FLAKE.md files. FLAKE.md stays the source of truth, `new-flake` and `rsi` update both in one change, and the validator fails when they differ (§12, Q5).
- **Picking:**
  1. Keep the flakes whose `when` fits the task.
  2. One fits: hand over.
  3. Several fit: take the most specific one. If that is still a tie, escalate once, naming both (escalate's block, kind `route`).
  4. None fits:
     - a one-off is handled directly;
     - a repeatable task gets ONE offer of `new-flake` (block kind `question`, with "handle it directly this time" as the first option);
     - unsure: treat it as a one-off and log it in `unrouted.md`.
  5. The owner names a flake ("use reviewer"): hand over without matching.
- **Past about 20 flakes:** INDEX.md is grouped under `## <group>` headings (from `group:`), each followed by one line saying what the group covers. The router reads the group lines first and the flake lines only under the groups that fit. It is still one file of about 3 lines per 2 flakes.
  - The validator requires `group` on every flake once there are more than 20, and warns past 50.
  - Past 50, rsi's "sprawl" check (§4.3) proposes merging or retiring flakes rather than adding a second index level.

### 2.7 Size budgets (validator-enforced)
| What | Budget |
|---|---|
| root SKILL.md | description ≤ 1024 characters; body ≤ 600 words |
| an ENTRY.md body | ≤ 800 words; a supporting file ≤ 300 lines |
| FLAKE.md body | ≤ 500 words; `when` ≤ 200 characters |
| `workflow.md` | ≤ 800 words |
| a doc | ≤ 1,500 words; INDEX.md ≤ 40 entries, each line ≤ 160 characters |
| `flakes/INDEX.md` | one line per flake, ≤ 220 characters each |
| MEMORY.md | ≤ 60 lines, each ≤ 400 characters |
| `memory/<topic>.md` | ≤ 300 lines |
| `memory/runs.md`, `memory/unrouted.md` | ≤ 200 lines (rsi trims, §4.4) |

These numbers are a starting point. rsi's "always-loaded text" check is how they get tuned, by root PR.

### 2.8 What loads when
| Moment | Loaded |
|---|---|
| Session start | the router's name and description only |
| Any task | the router body, `docs/INDEX.md`, `flakes/INDEX.md` |
| Hand over to flake X | `skills/memory/ENTRY.md`; root and X's MEMORY.md; X's `docs/INDEX.md`; `FLAKE.md`; X's required skills |
| During work | the docs and topic files whose "read when" fits; optional skills when used |
| Called flake | the same as a hand-over, in a fresh sub-agent; the caller loads nothing of it |
| End of a flake's run | `skills/rsi/ENTRY.md` (the run line; a retro only when triggered) |

## 3. The hand-over sequence (in the router, once for every flake)
1. **Start memory:** read `skills/memory/ENTRY.md`, then the root and the flake's MEMORY.md, then both docs indexes.
2. **Become the flake:** read `FLAKE.md` and load its required skills. Check `autonomy` versus `escalate`.
3. **Work:** follow FLAKE.md (and `workflow.md` if it links one). Write memory as you go (§5.1).
4. **End:** read `skills/rsi/ENTRY.md`, append the run line, run a retro if one is triggered, and finish (commit memory; at depth 0, open the staged PRs). Then give the report: escalate's format when the flake opted into escalate, otherwise a short "done / decided / open" list.

A **called** flake (§5.4) does the same in its sub-agent, with two differences: it never re-routes, and it never opens PRs or commits memory. It leaves both to the depth-0 flake that owns the task.

## 4. RSI in detail
### 4.1 Per run (every flake, every time)
- **Recorded:** one `runs.md` line (§2.5), and new facts in memory.
- **Staged at once:** only a direct **owner correction** of the flake's behaviour ("never do X", "always run Y first"). It's evidence enough on its own, and it goes to the stage as a doc or FLAKE.md change.

Everything else waits for a retro.

### 4.2 What triggers a retro (checked at the end of each run, from `runs.md`)
- 5 runs since the last `retro` line;
- the same signal on 2 runs since the last retro: `esc>0`, `fixes>0`, `viol>0`, outcome `failed` or `stopped`, or the same `skipped` skill;
- a size budget over 90 % (compaction is due);
- the owner asks.

Otherwise, no retro: the run line is enough.

### 4.3 What a retro checks (adapted from mattpocock's `retro`)
Each finding names its evidence: run lines, unrouted lines, or an owner quote.
- **Navigation:** files or facts the flake hunted for. Fix with a doc plus an INDEX line, or a memory pointer.
- **Automated checks:** a mistake a script could catch. Propose the check for the *project* repo in the report; flakes don't own project CI.
- **Standards:** a **mechanical** rule becomes a check; a **judgement** rule becomes a doc line. Read the existing docs first, so the finding is "the existing rule is unclear" rather than a duplicate.
- **Always-loaded text:** FLAKE.md, the router, the INDEX files and MEMORY.md, against their budgets. Look for **no-ops** (lines that don't change behaviour) and delete them.
- **Tool economy:** expensive or repeated calls.
- **Information access:** something the flake needed and could not get.
- **Flake-specific:**
  - **routing:** a wrong flake picked (owner redirect), or `when` lines too vague or overlapping;
  - **calls:** call chains that looped, failed or were always skipped, and `may_change` violations;
  - **autonomy:** escalations that should have been decisions, and decisions the owner reversed;
  - **memory hygiene:** stale, duplicated or contradicted facts, and rules hiding in memory (these move to docs);
  - **sprawl:** repeated `unrouted.md` lines become a **new flake proposal** (handed to `new-flake`, which asks the owner); flakes unused for 30 runs of their siblings, or 60 days, are proposed for retirement; overlapping flakes are proposed for merging.
- **Removal pass (mandatory):** every retro proposes at least one deletion or compaction, or states, with the measured sizes, that everything is within 75 % of budget.
- **rsi itself:** how many of the last retro PRs were merged, changed or closed. Repeated rejections are a finding about rsi, which may propose a root PR to change `skills/rsi/`.

### 4.4 Compaction
- **MEMORY.md** over 75 % of budget: merge duplicates, move details into topic files, move stale lines to `memory/archive.md`.
- **runs.md and unrouted.md:** keep the lines since the last two retro lines. Older ones are deleted, since git history keeps them and the retro lines summarise them.

Memory compaction is written directly (it is memory). Doc and FLAKE.md compaction is staged.

### 4.5 Where staged changes live
- **The stage:** one git worktree per task and tier, **outside the repo and outside every skills dir**:
  ```sh
  R="$(git -C <root> rev-parse --show-toplevel)"; N="$(basename "$R")"
  T="${XDG_STATE_HOME:-$HOME/.local/state}/flakes/$N/stage/<YYYYMMDD-HHMM>-<task>-<tier>"   # tier: flakes | root
  git -C "$R" worktree add -q "$T" -b "flakes/<YYYYMMDD-HHMM>-<task>-<tier>"
  ```
  - Each task gets its own worktree, so two flakes hosted by Orca at once never share one.
  - The flakes and root tiers are separate so they become separate PRs.
- **Which tier:** a path in `spec/upstream-paths.txt` (§6) belongs to the root tier. Everything else under `flakes/` and `docs/` belongs to the flakes tier. Memory paths are never staged.
- **Called flakes** stage into the caller's task worktree. The task name and stage path are passed in the call brief (§5.4).

### 4.6 The PR shape
- **One PR per tier per task**, opened only by the depth-0 flake at its end.
- **Before opening:** run `python3 check/validate.py "$T"` (when python3 and PyYAML are there; CI runs it anyway).
- **Title:** `flakes(<flake>[,<flake>]): <summary>`, or `root: <summary>`.
- **Body:**
  - `## Evidence`: the quoted run and unrouted lines, and owner quotes;
  - `## Changes`: per finding, its category, what changed and its evidence;
  - `## Removed`;
  - `## Budgets`: before → after word counts of everything always loaded;
  - for a root PR, `## Upstream`: whether it should also be proposed to psai.
- **Finish:** commit, push, `gh pr create`, `git worktree remove`. Never merge. Without `origin` or `gh`, keep the branch and say where it is.
- **Nothing staged: no PR.**

### 4.7 Guardrails against drift and bloat
- **Evidence or nothing:** every staged change cites at least 2 run or unrouted lines, or 1 owner correction. The validator can't check this, but the PR template makes it visible, and the owner merges.
- **At most 5 changes per retro PR.** Extra findings wait for the next retro.
- **Budgets fail CI.** A retro that grows always-loaded text must remove something too (the removal pass).
- **Owner decisions stick:** a closed or reverted rsi PR adds a root memory line (`rsi proposal rejected: <what>, <why if given>`), and rsi won't propose it again without new evidence.
- **Memory can't change behaviour:** rules found in memory are moved to docs by PR, never obeyed from memory.
- **Fixed by design:** rsi never changes which skills are mandatory, never merges, and never edits the live clone outside memory. Changes to `skills/rsi/` are root PRs like any other.

## 5. Shared skill contracts (ENTRY.md outlines)
### 5.1 `memory` (mandatory; loaded at every hand-over)
- **Description:** "Reads and writes the shared and per-flake memory. Use at the start of every flake run, and whenever you learn a fact worth keeping."
- **Reads:** root MEMORY.md, the flake's MEMORY.md, and topic files on demand.
- **Writes, directly in the live clone:** facts as MEMORY.md lines (newest first; details in `memory/<topic>.md`), and archive moves.
  - Shared facts go to the root MEMORY.md; facts about this flake's work go to its own.
  - Rules go to rsi, not memory.
- **Called flakes write their own flake's memory.** They report root-level facts to the caller, which writes them, so concurrent sub-agents don't edit the root file at once.
- **Commit (depth 0, at the end):**
  - `git -C <root> add -- MEMORY.md memory 'flakes/*/MEMORY.md' 'flakes/*/memory'`, then `git commit -m "memory: <task>"`;
  - `git pull --rebase` then `git push`, when `origin` exists.
  - These paths only, straight to the default branch, no PR (§12, Q4).
  - `.gitattributes` sets `merge=union` on MEMORY.md, `runs.md` and `unrouted.md`, so lines appended concurrently rebase cleanly.
- **Read-only install** (`git -C <root> rev-parse` fails, e.g. after `npx skills add`): nothing is written. Memory lines go into the report under `## Memory (not saved)`.

### 5.2 `rsi` (mandatory; loaded at the end of every flake run)
- **Description:** "Records the run and improves the flakes from evidence: run lines, retros, compaction, staged PRs. Use at the end of every flake run, and when the owner asks for a retro or a psai update."
- **Reads:** the flake's `runs.md` since the last retro, `memory/unrouted.md`, the conversation's escalations and corrections, and the budgets of everything always loaded.
- **Writes:** the run line and retro line (directly), staged changes (§4.5), and the PRs (§4.6).
- **Files:** `ENTRY.md` (§4.1–4.2), `retro.md` (§4.3–4.4), `stage.md` (§4.5–4.6), `upstream.md` (§6).
- **May hand to `new-flake`** to propose a flake (with evidence) or to retire one. The owner always decides through `new-flake`'s questions.

### 5.3 `escalate` (optional; opted in through `skills`)
- **Description:** "When and how a flake asks the owner, and the format of its final report. Use when a flake opted into escalate and must ask, or is finishing."
- **When to ask** (from 4.0, unchanged):
  - unclear and changes the outcome;
  - irreversible or visible to others;
  - against a doc rule;
  - stuck after 2 tries;
  - the scope grew.

  Otherwise decide, and record the decision and its reason in the report and memory.
- **The fixed block, built by a script** (a hard guarantee):
  `bash skills/escalate/block.sh --kind escalation|review|question|route --flake <name> --question "<one question>" --why "<why docs and memory can't settle it>" [--option "<recommended>" --option ...]`
  - It prints the `<<<FLAKE … >>>` block (4.0's block with `node:` renamed `flake:`).
  - It refuses an empty field, more than one `?` in the question, or more than 4 options.
  - Put the block at the end of the message and stop. The owner's next message is the answer.
- **The report:** `## Done`, `## Decided alone` (decision and reason), `## Escalated`, `## Open`, `## Memory`, `## Staged` (PR links). A handover note (§5.4) uses the same sections plus `## State` (branch, worktree, commit) and `## Next`.

**A flake without escalate** never asks in the middle of a task. Its `autonomy` decides what happens when it is stuck:
- **`decide-and-record`:** take the safest **reversible** option, record it in the report, the run line (`outcome=decided`) and memory, and go on. Irreversible or outward actions (push to a shared branch, delete, deploy, post) are never decided: they stop as below.
- **`stop-and-record`:** stop, leave the work on a branch or worktree, record what blocks it (report, run line `outcome=stopped`, memory), and end.

The router itself may always ask about a routing tie or a new-flake offer, using escalate's block format. Routing happens before any flake runs.

### 5.4 `handoff` (optional; opted in through `skills`, with `calls`)
- **Description:** "Runs another flake: call it as a fresh sub-agent and use its result, or pass it the task and finish. Use when a flake's FLAKE.md or workflow.md says to call or pass to another flake."
- **Call:** start a FRESH sub-agent in the foreground and wait for its result. Its prompt starts:
  > You were called as flake `<x>` by flake `<y>`, task `<task>`, chain `<a > y>`, stage `<path>`. Do not route this request and do not start other flakes except through handoff. Follow `<root>/flakes/<x>/FLAKE.md` per the router's hand-over sequence, then return your report.

  The brief follows: goal, inputs, what to return, and the base commit.
  - Claude Code: the Agent tool, `general-purpose`, not in the background.
  - opencode: the `task` tool, `subagent_type: general`.
  - omp: the `task` tool.
  - pi: `pi -p --no-session "<prompt>"` through bash. If that fails, play the flake yourself, re-reading its FLAKE.md and working only from the brief.

  This is 4.0's delegation table, without `PSAI_ROLE`.
- **Pass:** write the handover note (escalate's format, or the same sections inline), record the run line (`outcome=passed`), then continue in the same session as the target flake from step 1 of §3. A flake hosted by another Orca bot is passed by messaging that bot the note instead.
- **Guards:**
  - the target must be in the caller's `calls` (validator);
  - no flake twice in the chain (no cycles);
  - a depth of at most 3 (`call` and `pass` both count);
  - a called flake never re-routes the original request.

  A guard that refuses goes to the caller's escalate, or its autonomy fallback.
- **`may_change` (optional, if kept, Q3):** when the called flake's FLAKE.md sets it, the caller commits pending work, records `base`, and after the call runs `bash skills/handoff/check-diff.sh <FLAKE.md> "$base"` (4.0's script, trace line removed). On a violation it resets to `base`, re-calls once with the violation quoted, and escalates or stops after a second one.
- **Every called flake runs its own memory and rsi**, so each flake improves on its own. Only depth 0 commits and opens PRs.

### 5.5 `new-flake` (shared; loaded by the router, rsi, or the owner's request)
- **Description:** "Builds, changes or retires a flake with the owner, one question at a time, and stages it as one PR. Use when the router offers a new flake, rsi proposes one, or the owner asks to create or change a bot."
- **Asking rules (from 4.0):** one question per message in escalate's block (kind `question`), the recommendation first, never asking what's already answered.
- **New flake, topics in order:**
  1. purpose (one sentence);
  2. `when` (drafted from the task or the unrouted lines);
  3. what it reads (docs to write or reuse);
  4. skills (shared, bundled, `installed:`, vendor or not);
  5. does it call other flakes, and in what order (if yes: `calls`, handoff, and optionally `workflow.md`);
  6. `may_change`, if kept;
  7. escalate or which autonomy fallback;
  8. seed memory.
- **Examples, clearly marked "example, not required"** (`skills/new-flake/examples/`): a `task-manager` flake whose FLAKE.md says "call `planner`, then pass the plan to `coder`, then call `reviewer`; if the reviewer asks for changes, call `coder` again, at most twice, then stop and record", and a lone `reviewer` flake. No format is enforced beyond §2.3.
- **Builds in the stage (flakes tier):** `FLAKE.md`, `docs/` with INDEX.md, empty `MEMORY.md` and `memory/runs.md`, and the `flakes/INDEX.md` line. Then it runs the validator, and the PR is opened at task end by rsi's finish.
- **Change and retire flows** follow the same steps. Retiring deletes the folder and its INDEX line. Its memory is moved to `memory/archive.md` with `· moved` first.
- **First run in an empty repo:** offer to set up the owner's first flake, and print the optional global line for each tool (the owner adds it by hand).

## 6. Upstream updates (psai → a user's repo)
- **Creating the repo:** clone, so the user's repo shares psai's history. Then `git remote rename origin upstream`, then `gh repo create <you>/flakes --private --source . --push`. GitHub won't fork into the account that owns the original, and a fork would be public.
- **Ownership:** `spec/upstream-paths.txt` lists what psai owns:
  - `SKILL.md`, `skills/`, `spec/`, `guide/`, `check/`, `dev/`;
  - `README.md`, `AGENTS.md`, `CLAUDE.md`, `.github/workflows/flakes.yml`, `.gitattributes`.

  The user owns everything else: `docs/`, `MEMORY.md`, `memory/`, `flakes/`.
- **Why there are no conflicts:** psai's copies of the user-owned paths are placeholders (`docs/INDEX.md` with a header only, an empty MEMORY.md, `flakes/INDEX.md` with a header only, `memory/.gitkeep`). `dev/check-upstream.sh` freezes them by hash, so psai can never change them after 5.0, and a merge never touches the user's files. A conflict is only possible in a root file the user changed through a root PR.
- **The update** (`skills/rsi/upstream.md`, run when the owner asks, or offered by a retro when the last check, a root memory line, is over 30 days old):
  1. `git fetch upstream --tags`.
  2. Take the newest `v5.*` tag. Releases, not main.
  3. In a root-tier stage worktree, `git merge --no-ff <tag>`.
  4. On a conflict, keep upstream's version, re-apply the local change only if it is still needed, and list each one in the PR body. If unsure, escalate or stop.
  5. Run the validator, then open a root PR `root: psai <tag>` with upstream's changelog section.
- **A major format bump** (`flakes-format: 2.x`) ships a `spec/MIGRATING.md` section. The update PR includes the migration of user-owned files, so it touches the flakes tier too, and the PR says so.

## 7. Install
```sh
git clone git@github.com:you/flakes.git ~/src/flakes
ln -s ~/src/flakes ~/.agents/skills/flakes      # opencode, pi, omp
ln -s ~/src/flakes ~/.claude/skills/flakes      # Claude Code (omp and opencode dedupe by real path)
```
- **Update:** `git -C ~/src/flakes pull --rebase` (rebase because memory commits are local).
- **`npx skills add you/flakes -g`** works too, but it makes a read-only copy (§5.1; Q6).
- **The optional global line**, added by the owner, never by a script, to the files in §1:
  > Start every task with the `flakes` skill, unless your prompt says you were called as a flake inside a running task.

  The clause matters because Claude Code's sub-agents also read `~/.claude/CLAUDE.md`.
- **One repo per environment:** the work distro clones the work repo, the personal distro the personal one. Both install as `flakes`.

## 8. Orca
- An Orca bot hosts a flake with a SOUL.md of one paragraph:
  > You are flake `<name>`. Follow `<root>/flakes/<name>/FLAKE.md`, starting with the hand-over sequence in `<root>/SKILL.md` (skip routing).
- **Memory:** the formats are equal on purpose, so the bot's `MEMORY.md` and `memory/` can be **symlinks** to `flakes/<name>/MEMORY.md` and `memory/`. Orca and the flake then read and write one file. Otherwise SOUL.md says which memory is authoritative (the flake's).
- **Passing to a flake that another bot hosts** uses Orca messaging (§5.4). Nothing in the repo depends on Orca.

## 9. Checks
### 9.1 The validator (`check/validate.py <repo>`, python3 + PyYAML; it ships, and the user's CI runs it)
Structural only:
| Kind | Check |
|---|---|
| layout | exactly one `SKILL.md`, at the root, matched case-insensitively; no `.git` or worktree below the root; required files exist (`docs/INDEX.md`, `flakes/INDEX.md`, MEMORY.md; per flake `FLAKE.md`, `docs/INDEX.md`, `MEMORY.md`, `memory/runs.md`); docs folders are flat |
| frontmatter | SKILL.md: Agent Skills keys only, `name: flakes`, description ≤ 1024 characters and contains "Use when", a known `flakes-format` major; no `disable-model-invocation` anywhere; ENTRY.md: `name` = folder, a description; FLAKE.md: only the keys in §2.3, `name` = folder, `when` present, `autonomy` set if and only if `escalate` is not in skills, `calls` requires `handoff`, `may_change` is in {anything, tests, nothing} |
| references | every bare skill name resolves to a shared or bundled ENTRY.md, and no bundled name shadows a shared one; `installed:` names are listed in the output as "needs installed"; every `calls` target exists; every `flake:<name>` in `workflow.md` exists and is in `calls`; Markdown links resolve under the root, with no `..` out of it |
| indexes | each docs INDEX.md lists every doc exactly once, every listed doc exists, and each line matches the format; `flakes/INDEX.md` matches the `flakes/*` folders one to one, with `when` and `group` equal to their FLAKE.md |
| memory | MEMORY.md header and line format; topic files linked from it exist; `runs.md` and `unrouted.md` line format |
| budgets | §2.7 |
| scripts | `escalate/block.sh` and `handoff/check-diff.sh` tested in temp repos (in psai's own CI) |

- `--upstream` (psai only, `dev/check-upstream.sh`): the placeholders are unchanged (by hash), `flakes/` has no flakes, `docs/` has no docs, and memory is empty.
- Negative tests live in `dev/fixtures/` as **overlays** applied to a temp copy of the repo, so psai stores no second `SKILL.md`.

### 9.2 The no-AI install proof (`dev/prove-install.sh`)
- Runs in a temp HOME. psai is served over local smart HTTP (`git-http.py`), cloned, and installed with the two symlinks.
- **pi:** `loadSkillsFromDir` lists exactly `flakes`.
- **omp:** its discovery API lists exactly `flakes`.
- **opencode and Claude Code:** start the tool against `fake-model.py`, and assert that the first request's skill listing has `flakes` and its description, and no internal name (`memory`, `rsi`, `escalate`, …).
- With a test overlay that adds a flake, a bundled skill and a vendored `ENTRY.md`, nothing new appears.
- With the global line added, it reaches the request.
- An update is a commit pushed plus `git pull`, and the new description reaches the next request.
- Tools not installed are skipped with a note. CI runs only the validator, as in 4.0.

## 10. What goes, what ADRs 0012 and 0013 become
| Removed (4.0) | Replaced by (5.0) |
|---|---|
| `.claude-plugin/` (plugin, marketplace), `plugin.json`, `package.json` | none: clone + symlink; the version is `metadata.version` in SKILL.md, plus `v5.*` tags |
| `hooks/hooks.json`, `extensions/psai.ts`, `PSAI_ROLE`, `request-router/nudge.md` | the broad description, plus the optional global line; called flakes are told so in their prompt |
| `skills/request-router/` | root `SKILL.md` (router) |
| `skills/work/` (engine, `trace.sh`, the YAML runner) | none: flakes follow prose. `check-diff.sh` moves to `skills/handoff/` (optional, Q3); delegation per tool moves to handoff |
| `work/escalation.md` | `skills/escalate/ENTRY.md` + `block.sh` |
| `work/your-stack.md`, `$PSAI_STACK`, `~/psai-stack` | the repo is the router's own folder |
| the stage at `<git-dir>/psai-stage` | `$XDG_STATE_HOME/flakes/<repo>/stage/<task>-<tier>` |
| `skills/capture-knowledge/`, `knowledge/` (inboxes, facts, decisions, per-role knowledge) | `skills/memory/`, MEMORY.md + `memory/` (facts), `docs/` (rules, by PR) |
| `skills/retro/` | `skills/rsi/` |
| `skills/sync/` (channel updates) | `git pull`; `rsi/upstream.md` |
| `skills/customize-harness/` (SKILL, LAYOUT, FORMATS, patterns, template, `graph.py`, `link-skills.sh`) | `skills/new-flake/` (interview, examples); `spec/SPEC.md`; the repo itself is the template; `graph.py` dropped; two `ln -s` lines |
| `workflow-<stack>-*` skills, `workflow.yaml`, `steps/`, simulator cases, `scripts/workflows.py` | flakes; optional free-form `workflow.md` |
| roles (`may_change`, `model`, briefs), `<stack>-shared` | flakes called through handoff; FLAKE.md's optional `may_change`. Per-role model choice is dropped (a flake may say it in prose) |
| guides, templates | docs with INDEX.md |
| `<stack>-rules` | root `docs/` |
| `skill:path` refs, the stack-prefix rule, the three-manifest rule | root-relative paths and skill names; nothing to prefix; `metadata.version` |
| `evals/` (driver, graders, scenarios, results, cases) | removed (deterministic checks only); fixtures become `dev/fixtures/` overlays |
| `scripts/check.sh`, `check.py` | `check/validate.py` (ships) + `dev/check-upstream.sh` |
| `scripts/prove-tutorial.sh`, `git-http.py`, `fake-model.py` | `dev/prove-install.sh` and helpers |
| `docs/guide/`, `docs/decisions/` | `guide/`, `dev/decisions/` (`docs/` is now the owner's) |
| AGENTS.md (psai maintainer rules) | `dev/AGENTS.md`; the root AGENTS.md is for any flakes repo ("follow `spec/SPEC.md`, run `check/validate.py .`") |

- **0012** becomes "superseded in part by 0014".
  - **Still in force:** no CLI, no runtime, no build step; a script lives inside the skill that uses it, and only with a real guarantee; maintainer tooling never ships; refs instead of a resolver; copy, don't override.
  - **Superseded:** per-tool packaging, flat top-level skills, discovery by name, the nudge, `$PSAI_STACK`, the stage location, workflows as YAML, roles and knowledge layers, AI evals.
- **0013** was never merged and is superseded by 0014. Its discovery research is kept in §1 (and on the `plan-one-skill` branch). Its number stays reserved, and `dev/decisions/README.md` lists it as superseded.
- **Earlier ADRs** (0001–0011) move to `dev/decisions/` unchanged. 0005 (workflows as state machines) is marked superseded by 0014.
- **Nobody runs 4.0** (never installed), so there is no migration. Tag `v4.0.0` before the cut-over.

## 11. PR breakdown (in order; each small and passing CI)
PRs 2–6 only add files (new `ENTRY.md` folders don't collide with 4.0's skill names). PR 7 is the one cut-over, so `main` is never half-migrated.
1. **This ADR, accepted:** the owner's answers to §12 recorded. Docs only.
2. **Spec:** `spec/SPEC.md` (§2–3) and `spec/upstream-paths.txt`. Docs only.
3. **Validator:** `check/validate.py`, `dev/fixtures/` overlays (good and broken repos built on a temp copy), and a CI job that runs it on them next to 4.0's checks.
4. **Mandatory skills:** `skills/memory/ENTRY.md` and `skills/rsi/` (`ENTRY.md`, `retro.md`, `stage.md`, `upstream.md`), plus `.gitattributes`.
5. **Optional skills:** `skills/escalate/` (+ `block.sh` and its tests) and `skills/handoff/` (+ `check-diff.sh` if Q3 keeps it, and its tests).
6. **`skills/new-flake/`:** the interview, the examples, and vendoring.
7. **Cut-over:**
   - root `SKILL.md`, placeholders (`docs/INDEX.md`, MEMORY.md, `memory/`, `flakes/INDEX.md`), README, root AGENTS.md;
   - delete everything in §10's left column;
   - move the ADRs to `dev/decisions/` and maintainer rules to `dev/AGENTS.md`;
   - `dev/check-upstream.sh` and `.github/workflows/flakes.yml`;
   - set 0012's status; `metadata.version: 5.0.0`; tag `v5.0.0` after merge.
8. **Install proof:** `dev/prove-install.sh` (§9.2) across the four tools, which also settles Claude Code's "to be proven" cell.
9. **Guide:** `guide/tutorial.md` covers create your repo, install, first flake with `new-flake`, a second flake called by the first, a retro PR, and a psai update. Plus a short reference per file kind. `prove-install.sh` runs the tutorial's `sh` blocks.

## 12. Open questions (decisions for the owner, each with a recommendation)
1. **Keep the name "flake"?**
   - Against it: Nix flakes are well known in the same audience (dev tooling, `flake.nix`). In CI talk, "a flake" is a flaky test, and a task like "fix the flake in CI" reads as a bot name to the router.
   - For it: it's short, distinctive, and fine as a folder name.
   - **Recommendation: rename to "bot"** (`bots/<name>/BOT.md`, skill `bots`). The definition already says "a flake is a bot", it matches Orca's hosting model (BOT.md ≈ SOUL.md), and it collides with nothing technical. If the owner prefers a distinctive word, keep "flake". The plan is a find-and-replace either way, done before PR 2.
2. **The skill's name: fixed (`flakes`) in every copy, or chosen per user?**
   - A per-user name edits a psai-owned line, so every psai update risks a conflict there. Two names in one environment can't happen anyway (one repo per environment).
   - **Recommendation: fixed.**
3. **Keep the optional `may_change` on FLAKE.md** (checked by handoff after a call)?
   - It's the one cheap, hard limit left: a reviewer that must not edit code really can't. It costs one frontmatter key and 4.0's 35-line script.
   - **Recommendation: keep it, optional**, three values only.
4. **Memory commits straight to the default branch (no PR)?**
   - "Memory is written directly" means facts land without review. The alternatives are uncommitted memory, which is lost on a reset or a second machine, or a memory PR every task, which is noise.
   - **Recommendation: direct commits, memory paths only, with `merge=union`.** CI's memory-format check runs on `main` and catches a malformed line.
5. **The router reads `flakes/INDEX.md`, not every FLAKE.md.**
   - The brief said the router reads every frontmatter. One file is cheaper and scales with groups, and the validator keeps it exactly in sync.
   - **Recommendation: the INDEX** (FLAKE.md stays the source of truth).
6. **Is `npx skills add` a supported install?**
   - It copies files, so there's no git: memory and rsi can't save anything.
   - **Recommendation: clone + symlink is the one documented way.** `npx skills add` gets one line, as a read-only install for someone trying it out (memory goes into the report).
7. **Where psai's maintainer files live in the user's copy.**
   - ADRs, fixtures, the install proof and maintainer rules are in every clone.
   - **Recommendation: `dev/`, shipped inert** (no SKILL.md, never read by the router). A separate repo or branch would make "clone psai and merge its tags" harder.
