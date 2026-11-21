# 0011: psai is a framework; stacks are separate repos (2026-11-22)

Status: **proposed**. This is a plan for the owner to accept before anything is implemented. It supersedes [0007](0007-fork-model.md) once its PRs land. The number is 0011 because 0010 is taken by [0010-retro-sync-ledger.md](0010-retro-sync-ledger.md) (on `retro-sync-skills-session`, which this branch builds on).

## Decision
- **psai is the framework, installed once per machine.** It holds the router, the engine, the installer, the checks, the authoring skill (customize-harness), retro and sync, build and publish. It ships no content.
- **A stack is its own git repo,** made with `psai new-stack <name>` from a template. It has a `stack.yaml` and the content folders: workflows/, roles/, steps/, guides/, templates/, my-skills/, skills.yaml, knowledge/ and evals/.
- **Several stacks are installed at once** (`psai stack add|remove|update|list`). Every name is namespaced (`stack:thing`), and the router merges all the installed stacks' routing into one index.
- **The personal overlay stack, `me`, always wins:** it overrides any stack's file by name, so nobody forks a stack to adjust it.
- **Content is found by name** with `psai resolve`. Skills and plugins never hard-code `~/.psai/...` paths again.
- **Kept as is:** the routing model, workflow state machines and graphs, roles, steps, guides, templates, the skills registry, retro and sync, the escalation policy, one plugin per tool, and the test layers. Only WHERE content lives and HOW it is found change.
- **Why:** the owner wants people to build and publish their own stacks (like cursor/plugins `pstack`) and use several at once. A fork can carry only one stack, mixes framework and content in one history, and forces every user to merge upstream. pstack shows the other end: one stack shipped as a plugin with generated per-tool trees. psai keeps the framework separate so many stacks can share it, and still offers a pstack-style standalone build.
- **Source:** the owner's brief (task_eb7aa2007241); this plan.

---

## 1. Layouts

### 1.1 The framework repo (`noueii/psai`)
```
VERSION                       semver of the framework, e.g. 3.0.0 (the split release)
install.sh                    installs the framework only (links, plugins, `psai` command, migrations); idempotent, --dry-run, --uninstall
instructions/global.md        the framework's always-on rules (≤ 250 words)
skills/                       request-router, work (+ escalation.md, trace.sh, check-diff.sh), customize-harness (+ patterns/),
                              capture-knowledge, retro, sync. Reserved names: no stack may ship these.
plugins/                      claude/ (+ hooks), opencode/, pi/, omp/: one framework plugin per tool; each calls `psai context`
.claude-plugin/marketplace.json   the framework's Claude marketplace (one plugin: psai)
scripts/                      psai.py (the CLI), resolve.py (new), stacks.py (new: add/remove/update/list, pins),
                              index.py (new: merged routing index), harness.py (validate, context), skills.py (registry),
                              ledger.py, retro.py, sync.py, simulate.py, graph.py, build.py (new), check.sh, test-*.sh
migrations/                   NNNN-<slug>.sh, framework migrations, run once per machine
template/stack/               what `psai new-stack` copies (see 1.2)
schemas/stack.schema.json     the stack.yaml schema (check.sh and `psai check` use it)
evals/                        run.sh, driver.py, graders/, scenarios/psai/ (framework scenarios), fixtures/
  fixtures/stacks/example/    the neutral test stack (today's fixtures/harness-content, plus a stack.yaml)
  fixtures/stacks/other/      a second neutral stack: collisions, cross-stack refs, routing merge
  fixtures/stacks/me/         a neutral overlay with overrides
  fixtures/textkit/           the fixture repo (unchanged)
docs/decisions/               ADRs about psai itself
LAYOUT.md                     rewritten: the stack layout (what goes where inside ANY stack) and the home layout
README.md                     the framework: install, stacks, overlay, CLI
```
Removed from the framework repo: `workflows/ roles/ steps/ guides/ templates/ knowledge/ my-skills/` and their READMEs (they move into `template/stack/`), the LAYOUT owner column, `check.sh --upstream`'s fork rule (replaced by "the framework ships no content folder").

### 1.2 The stack template (`template/stack/`, copied by `psai new-stack`)
```
stack.yaml                    see section 2
README.md                     what the stack is for, how to add it, its workflows (graph block filled by `psai graph`)
instructions/stack.md         optional always-on rules for this stack's work (≤ 60 words, counted in the nudge budget)
workflows/                    README.md, ROUTING.yaml (created with the first workflow), <name>.yaml, <name>.cases.yaml,
                              ROUTING.cases.yaml, GRAPHS.md (generated)
roles/ steps/ guides/ templates/   README.md each; same formats as today
knowledge/                    README.md, INDEX.md, facts/, decisions/, roles/<role>/INDEX.md (the author's curated knowledge;
                              no inbox: inboxes live in the overlay, section 7)
my-skills/                    README.md; <name>/SKILL.md (this stack's own skills)
skills.yaml                   pinned skills from other people, as today (+ ignore:)
evals/                        README.md, scenarios/<name>.yaml, fixtures/ (the stack's fixture repos)
.github/workflows/psai.yml    CI: install the framework at the lowest supported version and run `psai check .`
.gitignore
```
A stack holds content only. **Adding a stack never runs its code:** no install hooks, no migrations. Scripts inside a stack's skills run only when an agent invokes that skill.

### 1.3 The home layout (one machine)
```
~/.psai/                      ($PSAI_HOME overrides it)
  framework/                  a clone of noueii/psai at a release tag, or a link to a dev clone (`install.sh` from a clone links it)
  overlay/                    the personal overlay stack `me`: a git repo, created on install, remote optional
    stack.yaml                name: me; plus `models:` and `disable:` (section 6)
    stacks.yaml               the installed stacks: name, source, ref (tag or commit), order, mode (pinned | dev)
    instructions/owner.md     your rules for every task (today's owner.md)
    overrides/<stack>/<kind>/<file>   your replacement for one stack's file (section 6)
    workflows/ roles/ ...     your own content, a stack like any other (`me:...`)
    knowledge/                your knowledge and ALL inboxes (section 7)
  stacks/<name>/              each installed stack: a clone at its pinned ref (pinned), or a link to your working clone (dev)
  state/                      today's .state/: ledger, stage worktrees (state/stage/<stack>/), reports, index.json, install
                              and migration records, drift baseline
~/.local/bin/psai             the CLI ($PSAI_BIN)
```
Because `stacks.yaml` lives in the overlay repo, a whole setup moves to a new machine with `git clone <your-overlay> ~/.psai/overlay && psai stack sync`.

## 2. `stack.yaml`
```yaml
schema: 1                          # stack.yaml format version; the framework reads schema N and N-1
name: acme                         # [a-z][a-z0-9-]{1,31}; unique on a machine; not psai, me or repo
version: 1.4.0                     # semver; `psai publish` tags v1.4.0
description: "Code review and release workflows for TypeScript services."   # ≤ 25 words; shown in the nudge
author: { name: Jane Doe, github: janedoe }   # github is where suggestion PRs go (section 7)
repository: https://github.com/janedoe/acme-stack
license: MIT
psai: ">=3.0 <4"                   # supported framework range (PEP 440 / semver range)
requires:                          # other stacks this one references; installed with it
  - { name: base, source: github:janedoe/base-stack, version: ">=1.0 <2" }
exports:                           # what OTHER stacks may reference; the overlay may override anything
  workflows: [review, release]     # usable as a handoff target from another stack
  roles: [reviewer]
  guides: [ts-style]
  templates: [pr-report]
  skills: [changelog]
  # `"*"` exports every name of that kind; a kind left out exports nothing
routing:
  priority: 50                     # tie-break when two stacks' routes both fit (higher first); the overlay can change it
models:                            # per-role defaults (section 8)
  default: balanced
  roles: { reviewer: strong, scribe: fast }
```
Required: `schema, name, version, description, psai`. Everything else is optional. `schemas/stack.schema.json` is the source of truth; `psai check` validates it.

## 3. Names and namespaces
- **Stack names** are unique per machine. Reserved: `psai` (the framework's skills and files), `me` (the overlay), `repo` (the project overlay `<repo>/.psai/`). `psai stack add <src> --as <name>` installs a stack under another name when two clash; references from other stacks then go through `requires:` with the alias.
- **A reference is `[stack:]<kind-folder>/<name>`**, the path inside a stack with an optional stack prefix. Inside stack `acme`, today's `step: steps/do.md` and `read: [guides/style.md]` keep working unchanged and mean `acme:steps/do.md`. Another stack's file is `base:guides/style.md`. Short forms where the kind is known: `role: reviewer`, `role: base:reviewer`, `handoff: base:triage`, and on the CLI `psai resolve role acme:reviewer`.
- **Workflows are `stack:workflow`** everywhere outside their own stack: in the nudge, the router, the trace and the ledger (`acme:review`).
- **Skills** in roles' and steps' `skills:` are bare names (as today) or `stack:name`. A bare name resolves in this order: the overlay's my-skills, this stack's my-skills, this stack's skills.yaml, the stacks in `requires:`, then any installed skill (the registry).
- **Collisions:**
  - within one stack, a name is unique per kind (check.sh, as today);
  - across stacks, names never collide because every reference is qualified or stack-local;
  - a reference to another stack's name that isn't in its `exports` fails `psai check` (the overlay is exempt);
  - framework skill names are reserved: a stack's `my-skills/work` fails `psai check`;
  - tool-visible skill names can collide (section 9.2).

## 4. Routing across stacks
- **The index:** `psai index` (run by `psai context`, cached in `state/index.json`, keyed by each stack's commit and the overlay's mtime) merges every enabled stack's workflows and ROUTING.yaml. For each stack it stores its description, priority, `instructions/stack.md`, and each workflow's `stack:name`, `when` and routing tree. Overlay `disable: [acme:release]` drops a workflow; overlay workflows are stack `me`.
- **The router (request-router skill, logic unchanged):**
  1. Run `psai route` to print the merged index: the stacks, then per stack its tree and its workflows' `when`.
  2. Pick the stack(s) whose description or workflows fit, then walk that stack's ROUTING.yaml as today.
  3. One match runs. Several: the overlay's `prefer:` rules first (`prefer: [{ if: "<kind of task>", use: acme:review }]`), then `routing.priority` (overlay can override per stack), then the order in `stacks.yaml`. Still a tie, or unsure between two: escalate (the existing rule "when unsure, escalate").
  4. No match but repeatable: escalate, offering customize-harness (which asks the target stack, section 10).
- **The nudge within budget:** the injected text stays global.md + owner.md + the routing line + workflow lines. Workflow lines are `- acme:review: <when>`. Budget: **≤ 300 words of workflow lines** (today about 8 words per workflow, so ~35 workflows). Over budget, the nudge collapses stack by stack, the lowest-priority stacks first, to `- acme (6 workflows): <description>` and adds "Run `psai route` for the full list." The overlay's own workflows are never collapsed. `instructions/stack.md` lines are injected only for stacks not collapsed; each is capped at 60 words. check.sh measures the nudge with the fixture stacks and fails above the budget.

## 5. `psai resolve` (the resolution API)
```
psai resolve <kind> <ref> [--from <stack>] [--project <dir>] [--all] [--json] [--write]
psai resolve <ref>                      # kind taken from the path, e.g. acme:roles/reviewer.md
kinds: workflow role step guide template skill knowledge file instructions
```
- **Prints** the absolute path of the winning file. `--all` prints every layer, winner first. `--json` adds `{stack, kind, name, path, layer, overridden_by, exported}`.
- **Layers, highest first:** `repo` (`<repo>/.psai/<stack>/<path>`, then `<repo>/.psai/<path>` for the overlay's own names) → `me` overrides (`overlay/overrides/<stack>/<path>`) → the stack itself → for knowledge only, additive layers are listed, not replaced (section 7).
- **`--from <stack>`** sets what a bare reference means (the stack whose file contains it). The engine always passes it.
- **`--write`** prints where a write for that ref belongs (the overlay, or the stage worktree of a dev stack) instead of the winner. capture-knowledge, customize-harness and retro use it.
- **Exit codes:** 0 found; 3 not found; 4 not exported (cross-stack reference to a private name); 5 ambiguous bare skill name (two candidates at the same level).
- Python API: `resolve.resolve(kind, ref, frm=None, project=None)`, used by every script below. `psai` startup is one Python process (~50 ms); the engine calls it a handful of times per node, so no daemon.

**Callers that must change** (today they build paths from `H` or `root`):

| Caller | Today | After |
|---|---|---|
| skills/request-router | reads `H/workflows/ROUTING.yaml`, `H/workflows/*.yaml` | `psai route` |
| skills/work | `H/workflows/<name>.yaml`, `H/roles/<r>.md`, `H/knowledge/roles/<r>/INDEX.md`, step and `read:` paths, `H/skills/work/...`, `H/instructions/owner.md` | `psai resolve workflow acme:review`, then `psai resolve --from acme ...` for each step, role, read and knowledge file; `psai resolve file psai:skills/work/escalation.md` |
| skills/work/trace.sh, check-diff.sh | `$PSAI_HOME`, `<repo>/.psai/workflows/$wf.yaml` | take `stack:workflow`; resolve through `psai resolve` |
| skills/customize-harness | `H/LAYOUT.md`, writes under `H` (stage) | asks the target stack (section 10), then `psai resolve --write`, `psai stage <stack>` |
| skills/capture-knowledge | `H/knowledge/...` | `psai resolve --write knowledge <stack>:roles/<r>/inbox.md` (always the overlay) |
| skills/retro, sync | `H/scripts/psai.py`, LAYOUT | `psai` only; targets from section 7 |
| plugins (all four) | `$PSAI_HOME/scripts/harness.py context`, `ledger.py` | `psai context` / `psai ledger` (found as `$PSAI_HOME/framework/scripts/psai.py`, else `psai` on PATH) |
| scripts/harness.py validate, context | one root | per stack, refs through resolve; context from the index |
| scripts/skills.py | psai's skills/, one my-skills/, one skills.yaml | per stack (section 9) |
| scripts/simulate.py, graph.py | `<root>/workflows` | `<stack>` (a name or a path) |
| scripts/ledger.py, retro.py, sync.py | `root/.state`, `root/knowledge/**/inbox.md` | `$PSAI_HOME/state`, the overlay's inboxes; workflows as `stack:name` |
| evals/driver.py | copies the harness, overlays content | builds a temp `PSAI_HOME` (framework link, the scenario's stacks, an empty overlay) |

check.sh adds a rule: no `~/.psai/` or `$PSAI_HOME/` path in any SKILL.md, plugin or step outside `psai.py` and the plugins' one bootstrap line.

## 6. The overlay (`me`)
- **What it may override:** any file of any installed stack, whole-file: a workflow, ROUTING.yaml, a role, step, guide, template, `instructions/stack.md`, a my-skill (the whole folder), and skills.yaml entries (by skill name). Place the replacement at `overlay/overrides/<stack>/<same path>`. It is found by name, so references to it don't change.
- **Keyed settings, merged (not files):** in `overlay/stack.yaml`:
  - `models:` per `stack:role` (section 8);
  - `disable:` workflows or whole stacks (`acme:release`, `acme`);
  - `prefer:` and `priority:` for routing (section 4).
- **Never overridden:** a stack's `stack.yaml` identity (name, version, exports, requires) and knowledge. Knowledge is additive (section 7). The framework's own files can't be overridden either; a change there is a PR to psai.
- **Drift protection:** when you override a file, `psai` records the stack's commit and the file's hash in `overlay/overrides/<stack>/.base.yaml`. On `psai stack update`, a changed original under an override is reported: "acme:roles/reviewer.md changed upstream since you overrode it; diff with `psai stack diff acme roles/reviewer.md`". Nothing is merged automatically.
- **Validation:** `psai check` validates an override in place of the original (the overridden workflow must still pass L0 and L2 with that stack's cases, or with the overlay's own cases next to it).
- **Project overlay `<repo>/.psai/`** stays (today's per-repo rule): same layout as the overlay (`<repo>/.psai/<stack>/<path>` overrides, `<repo>/.psai/<path>` adds); it is the most specific layer (see open question 2).

## 7. Knowledge, inboxes and where the retro writes
- **Read:** a role reads, in order, the stack's curated `knowledge/roles/<r>/INDEX.md`, then the overlay's `knowledge/<stack>/roles/<r>/INDEX.md`. `psai resolve --all knowledge acme:roles/reviewer/INDEX.md` lists both; work gives both to the role.
- **Inboxes always live in the overlay:** `overlay/knowledge/inbox.md` and `overlay/knowledge/<stack>/roles/<role>/inbox.md`. A pinned stack is read-only, and an inbox entry is local and personal until the retro judges it. The cross-machine inbox union that sync does today moves to the overlay repo.
- **The retro decides each finding's target** (deterministic first, then judgement):
  1. About the project: the final report (as today).
  2. Your preference or your environment (an owner correction, a tool, a path, a credential gap): the overlay, as knowledge, an owner rule or an override.
  3. About a stack's content (its workflow shape, a role missing a skill, a guide wrong for everyone) and the stack is **dev** in `stacks.yaml` (you author it; you work in its clone): staged in that stack's repo.
  4. Same, but someone else's **pinned** stack: by default it goes to the overlay as an override, so you get it now. The retro also drafts a **suggestion** for the author (`.state/suggestions/<stack>/<date>.md`, with the diff). It opens a PR from your fork of their repo to `author.github` only when you say yes (outward-facing, so it asks with the fixed block, kind `question`).
  5. About the framework: a suggestion for psai, same as 4.
- **One PR per target repo per task.** retro finish builds at most one branch for the overlay (if it has a remote), one per dev stack touched, and the suggestions you approved. Nothing changed: no PR, as today.

## 8. Model per role
- Role frontmatter gets an optional `model:`. Its value is a **tier** (`fast | balanced | strong`) or `<tool>:<model id>` pairs (`{claude: opus, opencode: anthropic/claude-opus-5-5, pi: claude-opus-5-5, omp: claude-opus-5-5}`).
- **Order, first set wins:** overlay `models.roles["acme:reviewer"]` → role frontmatter `model:` → stack.yaml `models.roles.reviewer` → stack.yaml `models.default` → the tool's current model.
- Tiers map to concrete ids in the overlay's `models.tiers` (`psai setup models` writes it, like pstack's setup-pstack; the framework ships a default map per tool).
- **work** passes the resolved model when it delegates:
  - Claude Code: the Agent tool's `model` (sonnet, opus, haiku);
  - pi: `pi -p --model <id>`;
  - omp and opencode: their `task` tools' agent or model argument, verified against the installed versions in the PR that adds it.

  Where a tool can't set it, work notes "model not settable in <tool>" in the final report and carries on.
- `psai resolve model acme:reviewer --tool claude` prints the result. `harness.py skills brief` keeps the skills; a sibling `brief` line adds the model.

## 9. Per-tool plugins and skills
### 9.1 One framework plugin per tool
The four plugins stay as they are (the same hooks and ledger calls), with three changes:
- they find the framework through `$PSAI_HOME/framework`, not `$PSAI_HOME/scripts`;
- the nudge comes from `psai context`, which reads the merged index, so a stack added or removed shows up in the next session with no reinstall;
- the Claude marketplace stays in the framework repo (`psai@psai`).

Stacks ship no plugin of their own. That is what `psai build --standalone` is for.

### 9.2 Skills from several stacks
- `install.sh` and `psai stack add|remove|update` link the skills into `~/.claude/skills` and `~/.agents/skills` as today. The sources are the framework's skills/, then each stack's my-skills/ and its fetched skills.yaml packs (`state/skills-cache/<stack>/<name>`), then the overlay's.
- **Tool-visible name collisions** (tools read skills by folder name, flat, and `name` must equal the folder):
  - the framework's names are reserved;
  - for any other name in two places, the overlay's copy gets the bare name, then the higher-priority stack's. The other copy is not linked bare. Roles still get it, because the skills brief always gives the SKILL.md path (0009), so the role uses the right stack's copy whatever the tool sees;
  - `psai check` warns stack authors to prefix their skill names (`acme-changelog`);
  - `psai stack list --skills` shows which copy each tool sees.
- The same skill pinned by two stacks at different refs is fetched twice, under `skills-cache/<stack>/<name>`. Each role's brief points at its own stack's copy, and the tool-visible link follows the collision rule.
- The registry (`psai skills`) gains a `stack` column. "Unmanaged" still means "in a tool folder and not linked by psai". Adopting a skill goes to the overlay (`me`) by default, or to a dev stack with `--to <stack>`.

## 10. customize-harness
It asks first: **"Which stack does this change?"**, offering
- the overlay (`me`): your own workflows and your adjustments to others' stacks; recommended for personal work;
- a stack you author (any `dev` stack);
- a new stack: runs `psai new-stack <name>` and switches it to dev.

Picking a pinned stack you don't author means an override in the overlay (and optionally a suggestion, section 7). Then the existing flow runs (interview, patterns, build, validate), in that stack's stage worktree (`psai stage <stack>`, the generalized stage of 0010). Validation runs `psai check <stack>`.

## 11. CLI
| Command | Does |
|---|---|
| `psai new-stack <name> [--dir <path>]` | copy `template/stack/`, fill stack.yaml (name, author from git config, psai range = current major), `git init`, add it as a dev stack |
| `psai stack add <src> [--ref <tag\|commit>] [--as <name>] [--dev]` | `src` = `github:o/r`, a git URL or a local path; check the psai range and `requires`; clone at the pinned ref (a branch is refused, as in skills.yaml) or link with `--dev`; record in stacks.yaml; link skills; rebuild the index. Shows the stack's description, exports and skill scripts before confirming (`--yes` skips) |
| `psai stack remove <name>` | unlink its skills, remove the clone (a dev link is only unlinked), keep its overrides (reported) |
| `psai stack update [<name>] [--to <ref>]` | move a pin to the newest tag in range (or `--to`); report changed originals under overrides; dev stacks: fast-forward only |
| `psai stack list [--skills] [--json]` | name, version, ref, mode, priority, workflows, exports, override count, out-of-range warnings |
| `psai stack sync` | install everything stacks.yaml lists (a new machine) |
| `psai stack diff <name> [<path>]` | the stack's change since the pin, or an override against its original |
| `psai resolve ...` | section 5 |
| `psai route` / `psai index` | print the merged routing / rebuild the index |
| `psai stage <stack>` | print (and create) that stack's stage worktree |
| `psai check [<stack>\|<path>] [--quick]` | L0 content + L2 simulate for one stack, resolving refs against installed stacks and its `requires`; no argument = every installed stack and the overlay. The framework's own tests stay `scripts/check.sh` |
| `psai eval <stack> [scenario...] [--tool ...] [--runs n]` | the stack's `evals/scenarios` in a temp `PSAI_HOME` with the framework, that stack and its `requires` (no overlay, no real HOME) |
| `psai build --standalone [<stack>] [--target claude,agent-plugins,pi,omp,opencode] [--out dist/]` | section 13 |
| `psai publish [<stack>] [--standalone]` | `psai check`, refuse a dirty tree or an existing tag, tag `v<version>`, push the tag; `--standalone` builds and attaches the packages to a GitHub release (`gh release create`), only after the owner confirms |
| kept from #4 | `install`, `update` (the framework only), `status`, `doctor`, `sync`, `retro`, `adopt`, `skills`, `ledger`, `context`, `graph`, `simulate`, `migrate` |

## 12. Versions and migrations
- The framework follows semver in `VERSION`; the split is **3.0.0**. Stacks declare `psai: ">=3.0 <4"`.
- `psai stack add` refuses a stack whose range excludes the installed framework.
- `psai update` (the framework) lists installed stacks whose range excludes the new version and refuses unless `--force`; forcing marks those stacks disabled until they update.
- `schema:` versions stack.yaml itself. The framework reads the current and the previous schema. `psai stack upgrade <name>` rewrites a dev stack to the current schema (staged, PR to that stack); a pinned stack on an old schema is reported to its author by suggestion.
- Framework migrations stay in `framework/migrations/`, run once per machine. **0002-fork-to-stacks** converts an existing fork clone:
  1. the fork's user-owned files (by today's LAYOUT owner column) go into the overlay: workflows, roles, steps, guides, templates, knowledge with inboxes, my-skills, skills.yaml, `instructions/owner.md`, `evals/scenarios/<theirs>`; references inside them get no prefix (they stay stack-local, now `me:`);
  2. `~/.psai` stops being a link to the clone and becomes the home of 1.3, with `framework/` cloned at the 3.0.0 tag;
  3. `.state/` moves to `state/`;
  4. the old clone is left untouched, with a note on how to delete it.

  `--to-stack <name>` puts the content into a new publishable stack instead, with an empty overlay. It is a dry run first, like install.sh.

## 13. `psai build --standalone`
For people who don't use psai: one stack plus a pinned copy of the framework runtime, as native packages in `dist/<stack>/`:
- **Claude Code:** a plugin (`.claude-plugin/plugin.json`, `skills/` with the framework skills and the stack's my-skills, `hooks/` from plugins/claude, `runtime/` with the framework scripts at the built version, `content/` with the stack) plus a `marketplace.json`. Claude namespaces it as `<stack>:<skill>`.
- **Agent Plugins** (the open `plugin.json` that Cursor reads, as in pstack): the same tree with its manifest.
- **pi:** a pi package (package.json with the extension and skills).
- **omp:** an omp plugin (extension + skills).
- **opencode:** an `install.sh` that drops the stub plugin and skills, as install.sh does today.

In a standalone build:
- `PSAI_HOME` is the bundle, holding one stack and an overlay folder created on first use;
- `psai` comes from `runtime/`;
- stack management commands are disabled;
- retro suggestions go to the stack's author.

Like pstack, CI fails when a committed `dist/` is stale (opt-in: `build.commit_dist: true` in stack.yaml).

## 14. What happens to PR #4's pieces (`retro-sync-skills-session`, 35bba3e)
| Piece | Fate |
|---|---|
| retro skill, `retro.py gather` | **kept.** gather reads workflows as `stack:name` and inboxes from the overlay |
| `retro.py finish` | **reworked:** one branch per target repo (section 7) instead of one fork branch |
| `ledger.py` + all four plugins' hooks | **kept.** State moves to `$PSAI_HOME/state`; the record holds `stacks: {name: version}` instead of one psai version, and workflows as `stack:name` |
| migrations runner (`sync.migrate`, `.state/migrations.json`) | **kept**, under `framework/migrations` |
| `psai.py` dispatcher | **kept**, gains the commands in section 11 |
| `doctor`, `status` | **kept** minus the update/upstream lines; plus one line per stack (version, ref, in range, overrides changed upstream) |
| `sync.py update` (ff-only of the live fork, inbox union) | **reworked**, split three ways: `psai update` fast-forwards the framework clone (no user files in it, so no inbox merge); `psai stack update` moves pins (dev: ff-only); the overlay's pull is ff-only with the inbox union |
| `sync.py upstream_ahead`, the merge of `upstream/<branch>` in `build_pr` | **removed:** there is no upstream fork any more. Replaced by "a newer stack version in range" and "a newer framework release" in `sync check` |
| `build_pr` | **reworked:** `build_pr(target, changes)` for any repo (overlay, dev stack, suggestion fork) |
| `user_owned` (LAYOUT's owner column) | **removed:** the target is "which stack root the path is under"; the overlay and dev stacks are writable, nothing else |
| stage worktree `.state/stage` | **reworked:** one per target repo, `state/stage/<stack>/` (`psai stage <stack>`) |
| drift adoption targets | **retargeted:** unmanaged skills → overlay my-skills/skills.yaml; rules in CLAUDE.md/AGENTS.md → `overlay/instructions/owner.md`; memory facts → overlay inbox. The fingerprints are unchanged |
| sync skill text | **rewritten:** check = framework release, each stack's newer version in range, overlay remote, migrations, unsynced sessions and staged changes, drift. One PR per target |
| `capture-knowledge` (inbox only), `customize-harness` (stage only) | **kept**, with targets from sections 7 and 10 |
| `test-sync.sh`, ledger checks, `retro`/`retro-sync` evals | **kept**, ported to the new home; the upstream-merge cases are replaced by stack-update cases |

## 15. Migrating this repo, the ADRs, docs and PRs
- **Content folders** (`workflows/ roles/ steps/ guides/ templates/ knowledge/ my-skills/`, their READMEs, LAYOUT's content rows) move to `template/stack/`. LAYOUT.md becomes "inside a stack" + "the home". `instructions/owner.md` → overlay.
- **ADRs:**
  - 0007 gets "Superseded by 0011";
  - 0003 (vanilla) still holds: the framework ships no stack, and the template is empty;
  - 0004 (layers) holds, plus "knowledge is additive across stack and overlay";
  - 0008 gets a note that the plugin reads the merged index;
  - 0009 gets a note on per-stack skills and collisions;
  - 0010 gets a note pointing to section 14.
- **Docs:** README is rewritten around "install the framework, add stacks, your overlay". AGENTS.md: "psai ships VANILLA and is meant to be forked" becomes "psai is a framework; content lives in stacks". Test content stays neutral in `evals/fixtures/stacks/`.
- **Tests:**
  - the L1 fork-merge test is replaced by "a framework update never touches stacks or the overlay" and "a stack update keeps overlay overrides and reports changed originals";
  - `check.sh --upstream` becomes "the framework ships no content folder and no stack".
- **PR #2** is already merged into main (`9b34e23`); nothing to retarget.
- **PR #3** (`psai-skills`) is based on `harness-v1`, which is fully in main: retarget it to `main` and merge it as is.
- **PR #4's branch** (`retro-sync-skills-session`): open it as a PR on `psai-skills` (then main) and merge it as is. Its fork-specific parts are reworked by PR 9 below, not before (open question 3). Both land under the fork model; every later PR is a refactor with tests green at each step.

## 16. Test plan
- **L0 (framework, `scripts/check.sh`):**
  - `resolve` against the three fixture stacks (example, other, me): every layer order, overrides, `--from`, exports (exit 4), not found (3), ambiguous skills (5), `--write` targets;
  - stack.yaml schema: valid, missing fields, a bad range, reserved names;
  - cross-stack refs in workflows, handoffs and `read:`;
  - no hard-coded `~/.psai` in skills or plugins;
  - the nudge budget and its collapse, deterministic output.
- **L1 (temp HOMEs, local bare git repos, no network):**
  - install the framework; `stack add` by tag and by commit (a branch is refused), `--as`, `--dev`, `requires`; out-of-range refused;
  - `stack update` (pins move, dev ff-only, overrides reported); `remove`; `sync` on a fresh home from stacks.yaml;
  - idempotent re-runs, `--dry-run`, uninstall (stacks and the overlay are never deleted);
  - skill linking with collisions (overlay wins, framework names reserved); per-stack skills caches;
  - migration 0002 from a fork clone with every user-owned kind, plus a dry run;
  - the framework update refuses on an out-of-range stack.
- **Plugins (`test-plugins.sh`):** each tool's nudge lists `example:` and `other:` workflows and changes after `stack add` without a reinstall; the ledger records stack versions.
- **Sync/retro (`test-sync.sh`):** one branch per target (overlay, dev stack); a suggestion is drafted but no PR opens without a yes; overlay inbox union across two clones.
- **L2:** `psai check <stack>` simulates each stack, overrides included.
- **L3 (keep it small, Claude Code first, 2 runs each):** the existing scenarios ported to `example`; plus
  - `two-stacks`: the router picks `other:` for its kind of task;
  - `overlay-override`: the overridden role's rule shows in the result;
  - `retro-target`: a personal correction lands in the overlay, a stack flaw drafts a suggestion and asks;
  - `customize-asks-stack`: customize-harness asks which stack first.
- **Build:** `psai build --standalone example` for each target. Claude: `--plugin-dir dist/example/claude` in a headless run gets the nudge (as evals do today). pi, omp and opencode: discovery in a temp HOME (`check.sh --discover`).
- **`psai eval example`** runs from a stack repo outside the framework.

## 17. PR breakdown (in order; each small enough to review, tests green at each)
0. Merge #3 (retarget to main); open and merge #4's branch as is.
1. **This ADR** (docs only).
2. **Resolver core:** `scripts/resolve.py`, `psai resolve`, stack.yaml loader and schema. A compat mode treats today's single root as stack `me`, so behaviour is unchanged. L0 tests with fixture stacks.
3. **Callers go through resolve:** work, request-router, capture-knowledge, customize-harness, retro and sync skills; trace.sh, check-diff.sh, harness.py, simulate, graph, skills brief; plugins call `psai context`. The no-hard-coded-path check. Still single root.
4. **Home layout + stack management:** `~/.psai/{framework,overlay,stacks,state}`, `stacks.yaml`, `psai stack add/remove/update/list/sync/diff`, install.sh installs the framework only, migration 0002 (fork → overlay). L1 tests.
5. **Multi-stack routing:** `psai index`/`route`, the namespaced nudge with its budget and collapse, prefer/priority/disable, request-router text, the ledger and trace as `stack:workflow`.
6. **Overlay overrides:** `overrides/<stack>/...`, `.base.yaml` drift reports, validation of overrides, the project overlay layout.
7. **Skills across stacks:** per-stack registry and caches, linking with collisions, adopt `--to`.
8. **Model per role:** frontmatter, stack defaults, overlay tiers, `psai setup models`, delegation per tool.
9. **Retro, sync, knowledge targets (#4 rework):** overlay inboxes, per-target stage and PRs, suggestions, the dev/pinned author rule, sync check for stack versions; the fork/upstream code removed.
10. **`psai new-stack` + template + `psai check|eval <stack>`; repo cleanup:** content folders out of the framework, LAYOUT/README/AGENTS rewritten, fixtures to `evals/fixtures/stacks/`, the 0007 supersede note, `check.sh --upstream` replaced. Release **3.0.0**.
11. **`psai build --standalone`, Claude target** (plugin + marketplace) and the build tests.
12. **Other build targets:** Agent Plugins, pi, omp, opencode.
13. **`psai publish`.**

PRs 2-3 are pure refactors under the fork model. PR 4 is the first user-visible change. Nothing is released before PR 10.

## 18. Risks
- **Untrusted content in the system prompt:** a stack's `when` lines, descriptions and `instructions/stack.md` are injected into every session. Mitigations:
  - stacks are pinned to tags or commits;
  - `stack add` shows what will be injected and which skill scripts exist before confirming;
  - `stack update` shows the diff;
  - injected text is capped per stack.
- **Skill name collisions** in flat tool folders silently hide one copy from the tool. Roles stay correct through the brief's path, but a user invoking a skill by name gets the winner. Reported by `stack list --skills` and `psai check`.
- **Nudge budget:** many stacks can crowd the context; the collapse keeps it bounded but makes routing depend on `psai route` for collapsed stacks (one extra call).
- **Overrides going stale** when stacks update; reported, never auto-merged.
- **Uneven per-tool model selection** (section 8); verified per tool in PR 8.
- **Migration 0002** touches the owner's real setup. It is dry-run first, the old clone is left untouched, and it is tested on copies only.
- **Python + PyYAML** become a requirement for standalone users too (open question 6).
- **Scope:** 13 PRs. PRs 2-3 can't be skipped (everything depends on resolve), but 11-13 can wait for real demand.

## 19. Open questions for the owner
1. **The overlay's name:** `me` (as above), or `local` or `overlay`?
2. **The project overlay vs your overlay:** should `<repo>/.psai/` (one repo) beat your personal overlay, as today's "most specific wins" says (recommended), or does "the personal overlay always wins" mean above it too?
3. **PR #4:** merge it as is under the fork model and rework its fork parts in PR 9 (recommended: it is green and the rework is contained), or trim the fork-only parts (upstream merge, owner column) before it merges?
4. **Suggestion PRs to other authors:** the retro asks you each time before opening one (recommended), or opens them on its own once you've enabled it per stack?
5. **Model per role:** tiers (`fast | balanced | strong`) mapped per tool in your overlay, with optional concrete per-tool ids (recommended), or concrete ids only?
6. **Standalone builds need python3 and PyYAML** on the user's machine. Acceptable for 3.0 (recommended), or should the runtime that ships in bundles be ported to Node, which all four tools already have?
7. **Finding stacks:** git URLs and `github:owner/repo` only (recommended for 3.0), or also a central index of published stacks (a psai "marketplace")?
8. **Stack dependencies (`requires:`):** in 3.0 with one pinned version per stack and a refusal on conflict (recommended), or leave them out of 3.0 and allow only stack-local references plus handoffs to exported workflows of installed stacks?
