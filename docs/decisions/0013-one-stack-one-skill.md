# 0013: one stack = one skill (2026-11-23)

Status: **proposed**, the plan only. Nothing here is built. The owner set the direction (below). This ADR plans how to build it and asks the owner to decide the open questions at the end. Once accepted, it supersedes most of [0012](0012-skills-only.md) (see "What 0012 becomes").

## Decision (the owner's)
Stop adapting psai to each tool. Define a standard instead: **one stack = one skill folder with ONE entry point** (its `SKILL.md`) for the whole AI coding stack.
- The folder holds the entry and internal folders: `workflows/`, `roles/`, `guides/`, `templates/`, `knowledge/` and `skills/`. Internal sub-skills in `skills/` are loaded by relative path from the entry and are never discovered on their own.
- **Install:** clone the stack and symlink that one folder into a tool's skills dir, or use `npx skills add`. **Update:** `git pull`. All per-tool plugins, manifests, nudge hooks and extensions go away.
- **Reliability without plugins:**
  - a broad, model-invoked description;
  - one OPTIONAL line the user adds to their tool's global instructions;
  - no manually triggered skills: agents run on their own and escalate only per the policy.
- **What psai becomes:** the standard, plus tooling to author stacks: a spec, a template stack and an authoring skill. psai itself ships **vanilla**, with no workflows and no roles.
- **Kept from 4.0:**
  - state-machine workflows and their graphs;
  - roles as briefs with diff limits;
  - the escalation policy and the fixed block;
  - the guides, templates and knowledge layers;
  - local-only capture, plus a retro at task end (one PR);
  - sync as a workflow step;
  - deterministic checks in CI only;
  - work and personal kept apart by WSL distro.
- **Source:** the owner's brief for psai 5 (task_de0c966b33e4, 2026-11-23).

**Why:** 4.0 still maintains five packaging channels: a Claude plugin with a marketplace and a SessionStart hook, an Agent Plugins manifest, a pi/omp package with a TypeScript extension, and opencode through `npx skills` plus an `instructions` line. It also ships six top-level skills that compete for the model's attention, and a naming convention (`workflow-<stack>-*`, `<stack>-rules`, `<stack>-shared`) that exists only because each tool merges skills into one flat list. A single folder with one entry needs none of that. Every tool already discovers a `SKILL.md` folder, and the entry decides everything else itself.

**Compared with pstack** (cursor/plugins `pstack`, read 2026-11-23): its entry `poteto-mode` routes each task to one of 22 playbooks and loads sibling skills by relative path (`../<name>/SKILL.md`). We take the shape (one entry that routes to playbooks and loads the rest by path) and change three things:
- pstack's siblings are top-level skills, each discovered on its own (39 of them); ours are internal and invisible.
- `poteto-mode` sets `disable-model-invocation: true` and is typed by hand; our entry is model-invoked.
- pstack's playbooks are prose checklists; ours stay state machines with checked edges and diff limits.

---

## 1. The standard (stack standard 1.0)

### 1.1 Folder layout
A stack is a git repo whose **root is the skill folder**. The clone is what you symlink.

```
acme/                         the stack = one skill; folder name = `name` in SKILL.md
  SKILL.md                    THE entry: the only file named SKILL.md anywhere in the folder
  README.md                   for people: what it is, install, update, the optional global line
  workflows/
    README.md                 the folder's rules (one line)
    change/                   one workflow: <name> is lowercase-hyphen
      workflow.yaml           the state machine (same schema as 4.0, refs re-based: 1.4)
      steps/<step>.md         steps
      cases.yaml              simulator cases (deterministic; was evals/cases/)
      GRAPH.md                optional diagram (graph.py)
  roles/<role>.md             role briefs (may_change, read, skills, model)
  guides/<guide>.md           prescriptive prose, attached with read:
  templates/<template>.md     exact output formats
  skills/                     internal sub-skills, never discovered
    work/ENTRY.md             the engine (from the template): runs a workflow node by node
    work/escalation.md        the fixed block
    work/trace.sh, work/check-diff.sh, work/graph.py   unchanged from 4.0
    capture/ENTRY.md          knowledge capture (was capture-knowledge)
    retro/ENTRY.md            the retro (was retro)
    sync/ENTRY.md             sync (git pull --ff-only of this clone, one PR)
    <name>/ENTRY.md           the stack's own or vendored sub-skills
    vendor.yaml               pins for vendored sub-skills (1.5)
  knowledge/
    INDEX.md, inbox.md, facts/, decisions/, roles/<role>/{INDEX.md,inbox.md}
  .github/workflows/stack.yml CI: psai's validator on every push (from the template)
```

Rules:
- **Exactly one `SKILL.md`, at the root.** Every internal sub-skill's entry file is `ENTRY.md`, with the same frontmatter shape (`name`, `description`). This is forced by opencode (§2): it scans `skills/**/SKILL.md` recursively, so any nested `SKILL.md` would surface as a separate, discoverable skill.
- **No nested git worktree, clone or copy of the stack inside the folder.** The stage moves out of `.git/` (§1.7), because opencode's scan includes dot folders.
- Every top-level folder has a `README.md`: one line on what belongs there, plus one example. These replace 4.0's `LAYOUT.md` rows as the in-place guide.
- Files used by one workflow only may live in `workflows/<name>/` (`roles/`, `guides/`, `templates/` under it). Shared ones live at the top. Same rule as 4.0, without the `<stack>-shared` skill.

### 1.2 File formats
These are unchanged from 4.0's `FORMATS.md`, except the refs:
- `workflow.yaml`: `start`, `defaults {max, on_exhaust}`, `nodes` with `step`, `role`, `human`, `fan_out`, `skill`, `next [{when, to, max}]`, and the special nodes `terminal`, `return: caller` and `handoff: <workflow>`. `handoff` now names a workflow folder (`handoff: review`), not a skill.
- A step: frontmatter `read:` and `skills:`, then prose.
- A role: frontmatter `may_change` (`anything` | `tests` | `nothing`), `read`, `skills`, `model`, then the brief.
- A guide is prose. A template is the format plus one filled example.
- Knowledge, the inbox entry and the fixed block are unchanged.
- `skill: <name>` on a node means an internal sub-skill (`skills/<name>/ENTRY.md`), e.g. `skill: retro`, `skill: sync`.
- `workflows/<name>/cases.yaml` uses 4.0's simulator-case format.

### 1.3 The entry SKILL.md contract
Frontmatter (Agent Skills fields only):
```yaml
---
name: acme
description: "acme's AI coding stack: routes every software task (feature, fix, refactor, review, docs, chores, questions about the code) to the right workflow, runs it with role agents and checks, and escalates only per its policy. Use for any software task, before acting on it."
metadata:
  stack-standard: "1.0"
  version: "0.3.0"
---
```
- `name` equals the folder name: lowercase, digits and single hyphens, at most 64 characters (the Agent Skills spec; pi warns otherwise, and opencode has a name-mismatch error).
- `description`: at most **1024 characters** (pi's and the spec's limit; Claude Code truncates at 1536 in its listing). Aim for 300 or fewer so it survives Claude Code's listing budget when many skills are installed. It must start with what the stack does and contain "Use for any software task". The validator checks length and that phrase.
- Never set `disable-model-invocation`.

Body sections, in this order, and nothing else:
1. **`## Role agents`** (1 line): "If your prompt says you are a role inside a running workflow, ignore this skill and follow your brief." This replaces 4.0's `PSAI_ROLE` and the nudge's last line.
2. **`## Route`**: one table row per workflow, `| name | use when | workflows/<name>/workflow.yaml |`, plus the 4.0 router's decision rules in five lines: match, repeatable-without-match (escalate and offer authoring), one-off (handle directly), ties, and unsure (escalate). The validator checks that the table and `workflows/*/` match one to one.
3. **`## Run`** (2 lines): "On a match, read `skills/work/ENTRY.md` and run the workflow from `start`. Never improvise a workflow."
4. **`## Rules`**: the stack's always-on rules (4.0's `<stack>-rules`), as bullets. Includes the escalation policy (when to ask; otherwise decide and log).
5. **`## Knowledge and changes`** (3 lines): capture findings with `skills/capture/ENTRY.md`; change workflows, roles, guides and rules only through the authoring skill; after a workflow, or a task that captured something, run `skills/retro/ENTRY.md`.

**Size budget** (validator-enforced):

| What | Budget |
|---|---|
| entry body | ≤ 1,200 words |
| Route table | one line per workflow; past 25 workflows, move the table to `workflows/INDEX.md` and have Route say to read it |
| an internal `ENTRY.md` | ≤ 500 lines (Claude Code's guidance for a SKILL.md) |
| a role brief | ≤ 800 words |
| a step | ≤ 400 words |

The numbers are a starting point. The retro's "always-loaded text" finding is how they get tuned.

**What loads when:**

| Moment | Loaded |
|---|---|
| Session start | the description only (every tool lists name and description) |
| Any task | the entry body (Route, Rules) |
| A workflow matches | `skills/work/ENTRY.md`, then the workflow's yaml, then each node's step and its `read:` files as the node is entered |
| A role node | the role agent gets its brief, the brief's `read:` files and `knowledge/roles/<role>/INDEX.md`; the main agent does not load them |
| Terminal node | `skills/retro/ENTRY.md`, and `skills/sync/ENTRY.md` only at a `sync` node |
| A finding | `skills/capture/ENTRY.md` |

### 1.4 Refs (how files and internal skills are named)
- **Every ref is a path relative to the stack root**: `roles/checker.md`, `workflows/change/steps/do.md`, `skills/tdd/ENTRY.md`. No `..`, no absolute paths, no `skill:path` across stacks. One base for every file is simpler for the agent than 4.0's "relative to the naming skill's folder". The entry says once: "every path in this stack is relative to the folder this SKILL.md is in."
- **Finding the root:** every tool tells the model where the skill lives:
  - Claude Code: "Base directory for this skill";
  - opencode: "Base directory for this skill";
  - pi and omp: the path of the `SKILL.md` they read.

  A symlink resolves to the clone, so `git -C <root>` works.
- **Internal sub-skills** are named by path (`skills/retro/ENTRY.md`) or, in `workflow.yaml`, as `skill: retro`. They never appear in a tool's skill list.
- **An installed third-party skill** is named `skill:<name>` (a name, no path) in a step's or role's `skills: {required, optional}`.

### 1.5 Third-party skills (mattpocock/skills, pstack, others)
Two ways, chosen per skill when the owner adds it:
- **Referenced if installed** (`skill:tdd` in `skills.optional`): the user installs it through its own channel. A missing optional skill is noted in the final report. A missing required one escalates (4.0 behaviour). Use this for skills the user also wants outside the stack, and for skills tied to one tool, such as most of pstack, which needs Cursor features and is manual-only (`disable-model-invocation`).
- **Vendored with a pin** (`skills.required: [tdd]`, which resolves to `skills/tdd/ENTRY.md`):
  - The authoring skill copies the upstream folder into `skills/<name>/` at a commit and renames its `SKILL.md` to `ENTRY.md`. It keeps the upstream `LICENSE` (copied in if the license sits at the repo root) and records the pin in `skills/vendor.yaml`:
    ```yaml
    - name: tdd
      source: github:mattpocock/skills
      path: tdd
      commit: 3f2c9a1…
      license: MIT
      digest: sha256:…        # over the vendored files, ENTRY.md mapped back to SKILL.md
    ```
  - The validator recomputes `digest`, so a hand edit of vendored code fails CI. Changing a vendored skill on purpose means un-vendoring it (it becomes the stack's own).
  - Updating a pin is an authoring task: fetch, diff, re-vendor, one PR.
  - Recommended for anything a workflow requires, because the stack then works with one install.
- A vendored skill whose text loads siblings by `../<name>/SKILL.md` (the pstack style) breaks after renaming. The authoring skill rewrites those links to `skills/<name>/ENTRY.md`, and the validator's link check fails any it missed.

### 1.6 Versioning the standard
- The standard is semver, written in `metadata.stack-standard` of the entry.
- **MAJOR** changes the layout or the entry contract. **MINOR** adds optional files or keys. **PATCH** is wording.
- psai's validator accepts every MINOR of the majors it knows, and fails a stack declaring a major it doesn't know.
- The template's engine sub-skills (`skills/work`, `capture`, `retro`, `sync`) are stamped with the standard version they came from (`metadata.stack-standard` in each `ENTRY.md`). The authoring skill's **upgrade** flow diffs a stack's engine against the current template and stages the update as one PR. It never overwrites a locally changed engine file without asking.
- The stack's own version is `metadata.version` plus optional `vX.Y.Z` tags. 4.0's three-manifest rule goes.

### 1.7 Where a stack writes
- **Knowledge inboxes:** `<root>/knowledge/inbox.md` and `knowledge/roles/<role>/inbox.md`, edited in place in the live clone and left uncommitted until the retro. Same as 4.0, but the clone is now found from the entry's own folder instead of `$PSAI_STACK`.
- **The stage** (everything else: authoring, retro, sync): a git worktree of the stack, **outside the skill folder**, at `${XDG_STATE_HOME:-$HOME/.local/state}/psai/<stack>/stage`, branch `psai/stage`.
  - 4.0 put it in `<git-dir>/psai-stage`, which is inside `.git/` and so inside the skill folder. opencode's `skills/**/SKILL.md` scan with `dot: true` would find the staged copy's `SKILL.md` and register a second `acme` skill.
- **Finishing:** commit, push a branch, `gh pr create`, remove the worktree, and never merge. This is 4.0's "Finish" section, unchanged.
- **A read-only install** (`npx skills add`, which copies files and leaves no git repo at the root): capture goes to the final report, and the retro drafts its PR body in the report instead of opening one. The engine detects this with `git -C <root> rev-parse`.

---

## 2. Discovery limits per tool (verified 2026-11-23)
How each claim was checked:
- **pi 0.80.2** (installed): read `dist/core/skills.js`, and ran its `loadSkillsFromDir` on a scratch stack with a nested `skills/sub/SKILL.md`. Only the root skill loaded.
- **pi 1.6.0** and **omp 19.1.1**: read the npm tarballs (`npm pack`, not installed).
- **omp 18.11.0** (installed): read `src/discovery/*.ts`.
- **opencode 1.18.30** (installed binary): read its embedded source.
- **Claude Code 2.1.330** (installed binary): read the strings for the description cap; nesting is per its docs.

| | Claude Code 2.1.330 | opencode 1.18.30 | pi 0.80.2 / 1.6.0 | omp 18.11 / 19.1 |
|---|---|---|---|---|
| user skill dirs | `~/.claude/skills/` | `~/.config/opencode/skill(s)/`, `~/.claude/skills/`, `~/.agents/skills/` | `~/.pi/agent/skills/`, `~/.agents/skills/` | `~/.omp/agent/skills/`, `~/.agents/skills/`, `~/.claude/skills/`, `~/.codex/skills/` |
| how deep | `<dir>/<name>/SKILL.md` (docs; to be proven in PR 7) | **recursive**: `skills/**/SKILL.md` for `.claude`/`.agents`, `{skill,skills}/**/SKILL.md` for its own dirs, follows symlinks, includes dot folders | recursive, but **stops at a folder that has `SKILL.md`**; skips dot folders and `node_modules` | **one level**: `<dir>/<name>/SKILL.md` only |
| nested SKILL.md inside our folder | expected ignored | **registered as another skill** (and a duplicate name logs a warning; the last one read wins) | ignored | ignored |
| description limit | listing truncates at 1536 characters by default (a setting raises it), plus a total listing budget | none found | 1024 (warns; still loads) | none found |
| symlinked folder | yes (4.0's `link-skills.sh` relied on it) | yes (`symlink: true`) | yes; dedupes symlink aliases by real path | yes; dedupes by real path |
| global instructions file (for the optional line) | `~/.claude/CLAUDE.md` | `~/.config/opencode/AGENTS.md` (or `instructions` in `opencode.json`) | `~/.pi/agent/AGENTS.md` | `~/.omp/agent/AGENTS.md` (omp also reads `~/.claude/CLAUDE.md`) |

What this means for the standard:
- **One `SKILL.md` per stack is required, not just tidy.** It is the only rule that works in opencode, and it makes the depth question moot everywhere else.
- **Install = two symlinks**, both to the same clone, named after the stack:
  ```sh
  git clone git@github.com:you/acme.git ~/src/acme
  ln -s ~/src/acme ~/.agents/skills/acme     # opencode, pi, omp
  ln -s ~/src/acme ~/.claude/skills/acme     # Claude Code (omp and opencode dedupe the second path)
  ```
  `npx skills add you/acme -g` also works (a root `SKILL.md` is a valid single-skill repo), but it makes a read-only copy (§1.7).
- **The optional global line**, the same text everywhere, appended by the user (never by a script) to the file in the table above:
  > Start every task with the `acme` skill, unless your prompt says you are a role agent inside a running workflow.

  The role-agent clause matters: Claude Code subagents also read `~/.claude/CLAUDE.md`.

---

## 3. Multiple stacks
Two stacks side by side would both say "Use for any software task". Nothing decides between them: no tool orders model-invoked skills by priority, and the model picks one or flips between them. 4.0 solved this with prefixes and the router loading every `*-rules` skill. Without a router outside the stacks, there is no neutral place to merge.

**Recommendation: one stack per environment**, which matches the WSL split: the personal distro installs the personal stack, and the work distro installs the work stack.
- A team stack is used either as is or as a fork (your work stack is a fork of the team's, and upstream changes arrive by PR).
- Reusing another stack's pieces means vendoring them (§1.5), not installing both.
- **Enforced lightly:** the entry's Route section says "If another installed skill also claims to route every software task, escalate once, naming both, before doing anything." `prove-install.sh` documents the rule. psai cannot detect a second stack in a tool it doesn't run.
- **Rejected:** precedence by name, or a "primary" marker. No tool honours either, and it would bring back 4.0's merge logic in prose.

---

## 4. What psai's repo becomes
psai follows its own standard: **the repo root is one skill, `psai`, the authoring skill.** You install it like a stack (two symlinks), and only while authoring. Its description is narrow ("Use when creating, changing or upgrading an AI coding stack"), so it doesn't compete with the stack's entry.

```
psai/
  SKILL.md                 the authoring skill: bootstrap, add/change a piece, vendor, upgrade (≤ 1,200 words)
  README.md                what psai is, install (clone + 2 symlinks), the standard in one paragraph
  spec/
    STANDARD.md            the normative standard 1.0: everything in §1, with examples
    FORMATS.md             file formats (from customize-harness/FORMATS.md, refs re-based)
    LAYOUT.md              where each kind of file goes (from customize-harness/LAYOUT.md)
  author/                  the authoring skill's internals, loaded by path from SKILL.md
    interview.md           the bootstrap interview (§6)
    patterns/*.md          the 8 patterns, moved as they are
    vendor.md              referencing or vendoring a third-party skill (§1.5)
    upgrade.md             moving a stack to a newer standard or engine
    mine-sessions.md       optional: drafting answers from past sessions (§6)
  template/                the vanilla stack scaffolded for a new user (no workflows, no roles)
    SKILL.md.tmpl          the entry with __NAME__ placeholders; renamed on scaffold (never a SKILL.md in psai)
    README.md, workflows/README.md, roles/README.md, guides/README.md, templates/README.md,
    knowledge/{INDEX.md,README.md}, skills/{work,capture,retro,sync}/…, skills/vendor.yaml (empty),
    dot-github/workflows/stack.yml, dot-gitignore
  scripts/                 maintainer + stack CI only (never needed at run time)
    check.sh               psai's own checks (--upstream) or a stack's (a path)
    check_stack.py         the validator (§7.1), with workflows.py (graph rules, simulator)
    prove-install.sh       the no-AI install proof (§7.2), with git-http.py and fake-model.py
  tests/
    fixtures/              stack overlays: applied on a scaffolded template, so no SKILL.md is stored
    textkit/               the tiny repo the proofs run in (from evals/fixtures/textkit)
  docs/guide/              tutorial + reference, rewritten for the standard
  docs/decisions/          ADRs
  .github/workflows/check.yml
  AGENTS.md, CLAUDE.md
```

**Vanilla check** (`check.sh --upstream`): psai has no `workflows/` and no `roles/`, the template's `workflows/` and `roles/` hold only their README, and the only `SKILL.md` in the repo is the root one.

### 4.1 ADR 0013 content: removed from 4.0, and the replacement

| Removed (4.0) | Replaced by (5.0) |
|---|---|
| `.claude-plugin/plugin.json`, `marketplace.json` | none: clone + symlink, or `npx skills add` |
| `plugin.json` (Agent Plugins) | none |
| `package.json` (pi package, read by omp) | none |
| `hooks/hooks.json` (SessionStart nudge) | the entry's broad description, plus the optional global line |
| `extensions/psai.ts` (pi/omp nudge), `PSAI_ROLE` | same; a role agent is told in its prompt, and the entry's first section says to ignore it then |
| `skills/request-router/` and `nudge.md` | the entry's `## Route` section |
| `skills/work/` (SKILL.md, `trace.sh`, `check-diff.sh`, `escalation.md`) | `template/skills/work/` (`ENTRY.md`, the same scripts, `escalation.md`), copied into every stack |
| `skills/work/your-stack.md`, `$PSAI_STACK`, `~/psai-stack` | the stack is the folder the entry lives in. The stage rules move into `skills/work/ENTRY.md` |
| the stage at `<git-dir>/psai-stage` | `${XDG_STATE_HOME:-~/.local/state}/psai/<stack>/stage`, outside the skill folder (§1.7) |
| `skills/capture-knowledge/` | `template/skills/capture/ENTRY.md` |
| `skills/retro/` | `template/skills/retro/ENTRY.md` |
| `skills/sync/` (per-channel update commands) | `template/skills/sync/ENTRY.md`: `git pull --ff-only` on the clone, then one PR |
| `skills/customize-harness/` | the root `SKILL.md` + `author/`. `LAYOUT.md` and `FORMATS.md` move to `spec/`, `patterns/` to `author/patterns/`, `template/` to `template/`, `graph.py` to `template/skills/work/` |
| `skills/customize-harness/link-skills.sh`, `scripts/link-skills.sh` | the two `ln -s` lines in each README |
| `workflow-<stack>-<name>` skills | `workflows/<name>/` folders |
| `<stack>-shared` skill | top-level `roles/`, `guides/`, `templates/` |
| `<stack>-rules` skill (and "your stack's rules win") | the entry's `## Rules` section; one stack per environment |
| `skill:path` refs | stack-root paths; `skill:<name>` only for installed third-party skills |
| the stack-name prefix rule | none: nothing internal is discoverable, so nothing can collide |
| the three-manifest version rule | `metadata.version` in the entry, plus tags |
| `evals/run.sh`, `driver.py`, `graders/`, `scenarios/`, `results/` (AI evals) | removed: deterministic checks only (the owner's decision) |
| `evals/cases/<workflow>.yaml` | `workflows/<name>/cases.yaml` |
| `evals/fixtures/stacks/`, `variants/` | `tests/fixtures/` as overlays on the scaffolded template |
| `scripts/check.py` | `scripts/check_stack.py` |
| `scripts/prove-tutorial.sh` | `scripts/prove-install.sh` (keeps `git-http.py`, `fake-model.py`) |
| the template's `.github/workflows/psai.yml` | `stack.yml`: the same job, which runs `check.sh <stack>` from a pinned psai tag |

**What we give up** (beyond 0012's list):
- **Auto-update through a tool's channel** (Claude plugin auto-update, `pi update`). Mitigation in §8.
- **Always-on injection.** The nudge was guaranteed text in every session; the entry is now chosen by the model, unless the user adds the optional line.
- **Mixing several stacks** in one environment (§3).
- **Pulling engine fixes from psai automatically.** The engine is now copied into each stack, so an engine fix reaches a stack only through the authoring skill's upgrade flow, as a PR.

---

## 5. Migration
- **Nobody runs 4.0:** it was never installed, and the owner's stack doesn't exist yet. So there is no user migration, no compatibility shim, and no 4.x → 5.0 upgrade script. 4.0 stays available at its tag (`v4.0.0`, to be tagged before PR 6 if it isn't already).
- **ADR 0012** gets the status "superseded in part by 0013".
  - **Still in force:** skills-only, no CLI, no runtime, no build step; helper scripts only inside the skill that uses them, and only with a real guarantee; maintainer tooling never ships; refs instead of a resolver; copy, don't override.
  - **Superseded:** the per-tool packaging, flat top-level skills, discovery by name prefix, the nudge, `$PSAI_STACK`, and the stage location.
- **AGENTS.md** is rewritten for the new layout. Its skill rules become: "one `SKILL.md` at the root; sub-skills are `ENTRY.md`; Agent Skills frontmatter only; never `disable-model-invocation`." The manifest and nudge-file rules are deleted. "Delegation covers Claude Code, opencode, omp and pi" stays (it lives in `template/skills/work/ENTRY.md`).
- **Docs:**
  - `docs/guide/tutorial.md` becomes "Build your stack": clone psai, symlink it, bootstrap `acme`, push, install the clone with two symlinks, add the optional line, update with `git pull`. `prove-install.sh` runs it.
  - Reference pages:
    - `stack.md` → the standard;
    - `rules.md` → the entry's Rules section;
    - `shared.md` → removed (top-level folders);
    - `skill.md` → internal and third-party skills, vendoring;
    - `cases.md` → cases only (no scenarios);
    - `workflow.md`, `step.md`, `role.md`, `guide.md`, `template.md`, `knowledge.md`, `escalation.md` → paths re-based.

---

## 6. The authoring flow (`psai` SKILL.md + `author/`)
The asking rules are unchanged from 4.0: one question per message, with the fixed block (kind `question`, node `customize`), options with the recommendation first, and never asking what's already answered.

**First: which stack?**
- If the current tool lists a skill whose `metadata.stack-standard` is set, that is the stack. Confirm its path once.
- If there is none, ask for its name, where it lives (`owner/name` on GitHub, or local only) and where to clone it (default `~/src/<name>`). Then scaffold from `template/`: copy, rename `SKILL.md.tmpl`, fill the placeholders, `git init`, first commit. Offer `gh repo create --private --push`, and print the install lines and the optional global line. Symlinking is left to the user, so nothing touches their tool dirs unasked.

**Bootstrap interview** (`author/interview.md`). Cover every topic before proposing anything:
1. the kinds of tasks handed to agents;
2. the steps of each, and where a human must look;
3. the roles and what each may change;
4. the checks that prove the work right;
5. when agents decide alone and when they must ask (this becomes `## Rules`);
6. what the final report holds;
7. third-party skills already in use (for each: reference it or vendor it);
8. which models are available.

**Patterns offered, never forced** (`author/patterns/`, unchanged from 4.0): separate roles, a checker that works from the spec, diff limits, loop limits, sizing, a handover report template, decide-and-log, and a retro → sync tail. Each is offered once, where it fits, with a one-line why. Only the ones the owner picks are added.

**Proposal:** a short summary for acceptance, covering nodes, edges, roles with `may_change`, models, human points, loop limits, reads and rules. The owner corrects; it is revised and asked again.

**Building:**
- Write in the stage (§1.7), never in the live clone: workflow folders, roles, guides, templates, the Route row, Rules, `cases.yaml` (every edge, limit and escalation), `knowledge/roles/<role>/INDEX.md`.
- Self-check by running `scripts/check_stack.py` from the psai clone when python3 and PyYAML are there. Otherwise walk the rules by hand; CI runs them on the PR anyway.

**Writing to the stack:** in the stage only. The retro (or a `sync` node) at the end of the task finishes it as one PR on the stack repo, and the owner merges. The authoring skill never commits to `main` and never merges.

**Other flows**, each one question at a time:
- **Add or change one piece:** what and why, then the scope (rule, one workflow, shared), then where, then build. A rule for one repo still goes to that repo's AGENTS.md.
- **Vendor or reference a third-party skill:** `author/vendor.md`.
- **Upgrade the stack:** `author/upgrade.md`, covering the standard version and the engine files.

**Mining past sessions (optional input).** With the owner's yes (a fixed block), `author/mine-sessions.md` reads the local transcripts of the current environment:
- Claude Code: `~/.claude/projects/*/*.jsonl`;
- pi: `~/.pi/agent/sessions/`;
- omp: its session store under `~/.omp/agent/`;
- opencode: `~/.local/share/opencode/opencode.db`.

The exact paths are re-verified in PR 5. The flow drafts answers to the interview topics (recurring task kinds, owner corrections, repeated checks, where the owner stepped in) and offers them as pre-filled options. Raw transcripts are never copied into the stack, and only the owner's accepted answers are written. pstack's `automate-me` does the same for a mode skill.

---

## 7. Checks

### 7.1 Deterministic validation of a stack (`scripts/check_stack.py <stack>`)
| Kind | Check |
|---|---|
| format | exactly one `SKILL.md`, at the root; Agent Skills frontmatter only; `name` = folder (or repo) name; description ≤ 1024 characters and contains "Use for any software task"; no `disable-model-invocation` anywhere; `metadata.stack-standard` is a known major; every sub-skill is `skills/<name>/ENTRY.md` with `name` = `<name>` |
| entry contract | the five sections in order; the Route table matches `workflows/*/` one to one; every path in the entry resolves |
| links | every ref in `workflow.yaml`, steps and roles resolves under the root, with no `..`; Markdown links in every `.md` resolve; `skill:<name>` refs are listed in the final report's "needs installed" line (they can't be resolved offline) |
| graph rules | unchanged from 4.0 (`workflows.py`): reachable from `start`, every path can end, every automatic loop limited, `handoff` names an existing workflow, `skill:` nodes name an existing sub-skill; `cases.yaml` walks pass |
| roles | `may_change` ∈ {anything, tests, nothing}; `model` is a tier or a per-tool map |
| vendoring | each `vendor.yaml` entry exists, has a license, and its digest matches |
| size budgets | §1.3 table |
| layout | every top-level folder has a README.md; no nested git worktree or `.git` below the root's own |

`check.sh` also keeps 4.0's script tests in temp repos (`check-diff.sh`, `trace.sh`, `graph.py`), now against the template's `skills/work/`. It keeps "the checks catch broken stacks", rebuilt on overlays. And it scaffolds the template exactly as `SKILL.md` says, then validates the result.

### 7.2 No-AI install proof (`scripts/prove-install.sh`)
- Runs in a temp HOME, never the real one.
- psai and a scaffolded test stack are served over local smart HTTP (`git-http.py`), cloned, and installed with the two symlinks.
- Then, per tool, still without a real model:
  - **pi:** `loadSkillsFromDir` on `~/.agents/skills` lists exactly `acme`, not `work`, `retro` and so on.
  - **omp:** the same through its discovery API (or `omp` with the fake model).
  - **opencode, Claude Code:** start the tool against `fake-model.py`. It records the first request, and the proof asserts that `acme`'s name and description are in the skill listing, that no internal sub-skill name appears, and that `psai` is listed.
- Each tool is also run once with the optional global line in its global file, and the proof asserts the line reaches the request.
- An update is a commit pushed to the local server plus `git pull` in the clone; the proof asserts the new description reaches the next request.
- Tools not installed are skipped with a note. CI runs only the validator, because the four tools aren't in CI (same as 4.0).

---

## 8. Risks and mitigations
| Risk | Mitigation |
|---|---|
| **The model doesn't pick the entry skill** (no nudge any more) | the description leads with "Use for any software task, before acting on it" and lists task kinds; the optional global line, set up by the authoring skill's last bootstrap step, makes it near-certain; no competing broad skills (one stack per environment, psai's description is narrow); the proof shows the description reaches every tool. A pick-rate measurement needs AI evals, which the owner ruled out, so the retro's "routing" finding is the feedback loop |
| **The entry SKILL.md grows** with workflows and rules, and costs context every task | the §1.3 budgets are enforced in CI; Route is one line per workflow and moves to `workflows/INDEX.md` past 25; the engine, roles, guides and knowledge load only when needed (§1.3 "what loads when"); the retro flags always-loaded text |
| **Tools that scan nested folders** (opencode today; others could start) | exactly one `SKILL.md` and sub-skills named `ENTRY.md`, both validator-enforced; the stage moves out of the folder; template stored as `SKILL.md.tmpl`; psai's fixtures are overlays with no `SKILL.md`; the install proof asserts no sub-skill shows up |
| **Losing auto-update** (plugins and packages updated themselves) | update is `git pull`, which the template's `sync` sub-skill runs at a `sync` node (the retro → sync tail pattern) and reports when it can't fast-forward; engine upgrades from psai arrive as a PR via the authoring skill's upgrade flow; the stack README says "update = git pull" in one line |
| A user installs two stacks anyway | the entry's escalate-once rule (§3) |
| Vendored skills drift or carry broken sibling links | the digest check and link check (§7.1); upgrading is an authoring task with a diff |
| Symlinks on Windows (non-WSL) | out of scope: the owner works in WSL distros. `npx skills add` (a copy) is the fallback, read-only per §1.7 |
| A read-only install silently loses knowledge | the engine detects a non-git root and writes captures into the final report, saying why |

---

## 9. PR breakdown (in order; each passes `scripts/check.sh --upstream`)
1. **This ADR, accepted.** The owner's answers to §10 are recorded in it. Docs only.
2. **The spec:** `spec/STANDARD.md`, `spec/FORMATS.md`, `spec/LAYOUT.md` (standard 1.0), written from §1. Nothing removed yet. Docs only.
3. **The validator:**
   - `scripts/check_stack.py` + `workflows.py` re-based on stack-root refs;
   - `tests/fixtures/` overlays and a minimal hand-written stack to run them on;
   - CI calls it.

   4.0's checks keep running beside it.
4. **The template:**
   - `template/` (vanilla), with the engine sub-skills ported from 4.0's `work`, `capture-knowledge`, `retro` and `sync`: paths re-based, the `$PSAI_STACK` removal, the stage moved, the read-only install case added;
   - `trace.sh`, `check-diff.sh` and `graph.py` moved;
   - `check.sh` scaffolds it and validates the result.
5. **The authoring skill:** root `SKILL.md` + `author/` (interview, patterns moved, vendor, upgrade, mine-sessions), with the scaffold commands tested by `check.sh` the way 4.0 tests `customize-harness`'s.
6. **Remove 4.0:**
   - delete `skills/`, `.claude-plugin/`, `plugin.json`, `package.json`, `hooks/`, `extensions/`, `scripts/link-skills.sh`, the AI evals, `scripts/check.py`;
   - move `evals/fixtures/textkit` to `tests/`;
   - rewrite `--upstream` (vanilla + one `SKILL.md`), README, AGENTS.md;
   - set 0012 to "superseded in part"; `metadata.version: 5.0.0`.
7. **The install proof:** `scripts/prove-install.sh` (§7.2) across the four tools, which also settles the "to be proven" cells in §2.
8. **The guide:** the tutorial and the reference rewritten; `prove-install.sh` runs the tutorial's `sh` blocks the way `prove-tutorial.sh` did.

PRs 2–5 only add, and PR 6 is the one cut-over, so `main` is never half-migrated. PRs 7 and 8 could merge into one if the tutorial is short.

---

## 10. Open questions (decisions for the owner)
1. **Is psai's repo root itself the authoring skill (`psai/SKILL.md`, installed like a stack), or a subfolder (`psai/author/SKILL.md`)?**
   - Root means psai follows its own standard and has one install recipe for everything. It costs that psai's fixtures and template can never contain a `SKILL.md`, so they become overlays and `.tmpl` files.
   - **Recommendation: root.**
2. **Does every stack carry its own copy of the engine** (`skills/work`, `capture`, `retro`, `sync` from the template), **or reference psai's at run time?**
   - A copy makes the stack self-contained (one install, works without psai) and versioned with it. Engine fixes then arrive by an upgrade PR, not automatically.
   - Referencing would need psai installed beside every stack, which breaks "one skill".
   - **Recommendation: copy, with the upgrade flow.**
3. **Must psai be installed to change a stack mid-task** (when the router finds a repeatable task with no workflow, or the retro proposes a rule)?
   - Alternative: each stack carries a small authoring sub-skill.
   - **Recommendation: psai installed beside the stack, with a narrow description.** One authoring copy avoids skew between stacks, and the entry's escalation says "install psai (two symlinks) to set this up" when it's missing.
4. **One stack per environment, or side-by-side stacks with a precedence rule?**
   - **Recommendation: one per environment** (the WSL split), with the escalate-once guard. Reuse happens by forking or vendoring.
5. **Is `npx skills add` a supported install, or is clone + symlink the only one?**
   - **Recommendation: document clone + symlink as the way.** Mention `npx skills add` in one line as a read-only install for people who only consume a team stack: it doesn't capture knowledge or open retro PRs.
6. **Delete the AI eval tooling** (`evals/run.sh`, `driver.py`, `graders/`, `scenarios/`), **or keep it as an unshipped manual extra?**
   - The brief says deterministic checks only; AGENTS.md today calls the evals optional and manual.
   - **Recommendation: delete in PR 6.** Its only unique value is measuring how often the entry is picked, and that can be rebuilt later if routing proves unreliable.
7. **The internal entry file name: `ENTRY.md`?** Anything except `SKILL.md` works, given opencode's recursive scan.
   - **Recommendation: `ENTRY.md`.** It is distinct, case-safe on case-insensitive filesystems (unlike `skill.md`), and says what it is.
