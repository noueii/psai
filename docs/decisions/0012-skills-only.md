# 0012: psai is a skills-only pack (2026-11-23)

Status: **accepted** by the owner (2026-11-23); built in psai **4.0.0** as four stacked PRs (the last section). It supersedes [0011](0011-framework-and-stacks.md)'s runtime: the `psai` CLI, the home `~/.psai`, the overlay and its override engine, the merged routing index and the standalone build. It keeps 0011's idea that content lives in stacks, which are separate repos.

## Decision
psai 3.0 had grown into a program to maintain: about 7,300 lines of Python and shell (the `psai` CLI and its resolve, stacks, index, engine, models, ledger, sync, retro, build and publish modules, a 415-line `install.sh`, migrations, and the `~/.psai` home). The owner wants no custom CLI or runtime. psai 4 follows [mattpocock/skills](https://github.com/mattpocock/skills):
- **Skills are plain Markdown.** Everything a user gets is a skill in a flat `skills/<name>/SKILL.md` (name equals the folder): `request-router`, `work`, `customize-harness`, `capture-knowledge`, `retro`, `sync`. The agent does the work by reading files and running git and gh. Nothing calls a psai command.
- **A helper script lives inside the skill that uses it, and only when it gives a real guarantee:** `work/check-diff.sh` (a role's diff stays within `may_change`) and `work/trace.sh` (a move follows an edge of the workflow, and no role node is left without a diff check).
- **The repo is the package.** Each tool installs it through its own channel: a Claude Code plugin and marketplace, an Agent Plugins `plugin.json`, a pi package (`package.json` `"pi"`, which omp also reads), `npx skills add`, or `scripts/link-skills.sh` for development. There is no build step. Publishing is pushing a commit or a tag.
- **Content is skills too.** A workflow is a self-contained skill folder, `skills/workflow-<name>/` (SKILL.md, `workflow.yaml`, `steps/`, and any roles, guides and templates it alone uses). Shared roles, guides and templates live in a `<stack>-shared` skill; always-on rules in a `<stack>-rules` skill. A file names another skill's file as `skill:path`. `request-router` finds workflows by name (every skill named `workflow-*`) among the skills the tool already sees: there is no index.
- **A stack is a skills repo in the same layout as psai.** Several stacks combine because each tool merges its installed skills (Claude Code namespaces plugin skills as `plugin:skill`). Collisions are avoided by naming: a stack prefixes its skills with its name (`acme-shared`, `acme-rules`, `workflow-acme-review`). Your personal layer is just your own stack.
- **Your stack's clone is the one writable place.** Knowledge (inboxes, facts, decisions) and staged changes live in the git clone at `$PSAI_STACK` (default `~/psai-stack`). Changes are staged in a git worktree of it (`<git-dir>/psai-stage`, branch `psai/stage`), and the retro or sync turns them into one PR the owner merges. `work/your-stack.md` is the one place that says so.
- **Model per role** is the role file's `model:` (a tier or ids per tool); `work` passes it when it starts the role agent, where the tool allows.
- **Maintainer tooling is not shipped.** Frontmatter and layout checks, the workflow simulator and the evals are repo scripts (`scripts/`, `evals/`) that run locally and in GitHub Actions. New stacks get the same CI from the stack template inside `customize-harness`, which scaffolds a stack; there is no `psai new-stack`.
- **Why:** a CLI and a home layout are a second product to install, migrate and debug on every machine, in every tool. Skills are the one format every tool already installs, updates and merges. What the runtime did either moves into the agent's instructions (resolving a file, staging, finishing a PR), into a tool's own channel (installing, updating, merging several stacks), or is given up (below).
- **Source:** the owner's brief for psai 4.0 (task_fa3ee0fd8423, 2026-11-23).

## What is removed, and what replaces it
| Removed (3.0) | Replaced by (4.0) |
|---|---|
| `psai` CLI (`scripts/psai.py`) and its subcommands | the skills' own instructions; the agent reads files and runs git and gh |
| `psai resolve`, `psai node`, `scripts/resolve.py` (find a file by name across stacks) | refs: `path` in the same skill folder, or `skill:path`; the tool already knows where each skill is |
| `psai route`, `scripts/index.py` (the merged routing index, `ROUTING.yaml` trees, priorities, `prefer`) | `request-router` lists the `workflow-*` skills the tool shows and matches their descriptions; a `*-rules` skill may say which to prefer; a tie escalates |
| `scripts/engine.py`, `scripts/harness.py` (validation, the nudge text) | `work`'s SKILL.md; the static nudge `skills/request-router/nudge.md`; validation moves to the maintainer checks |
| `psai trace`, `psai check-diff` wrappers | `work/trace.sh` and `work/check-diff.sh`, run by path from the `work` skill's folder |
| `~/.psai` home: `framework/`, `overlay/`, `stacks/`, `state/` | none. The tools hold installed skills; your stack's clone (`$PSAI_STACK`) holds your content and knowledge |
| overlay `nostack` and the override engine (`overrides/<stack>/<path>`, `.base.yaml`, `psai stack override`) | your own stack. To change someone else's workflow, copy it into your stack under your own name |
| `psai stack add/remove/update/list/sync`, `scripts/stacks.py`, `stacks.yaml`, pins, `requires:` | each tool's install channel (`claude plugin install`, `pi install`, `omp plugin install`, `npx skills add`) |
| `stack.yaml`, `schemas/stack.schema.json` | the native manifests: `.claude-plugin/plugin.json` and `marketplace.json`, `plugin.json`, `package.json` |
| `exports:` (what other stacks may use) | none: any installed skill's files can be named with `skill:path` |
| `psai stage`, the stage worktree in `state/` | a git worktree of your stack's clone, `<git-dir>/psai-stage` (`work/your-stack.md`) |
| `psai retro gather/finish/suggest`, `scripts/retro.py` | `retro`'s SKILL.md: the trace file, `git diff` of the inboxes, the conversation; it finishes with git and `gh pr create`; suggestions to another stack's author are drafted in the report |
| `psai sync check/update/drift/pr`, `scripts/sync.py` | `sync`'s SKILL.md: `git pull --ff-only` on your stack, each channel's own update command, one PR |
| session ledger (`scripts/ledger.py`, SessionEnd hook, "earlier sessions without a retro" in the nudge) | none (given up, below) |
| `scripts/models.py`, `psai setup models`, `models:` in `stack.yaml` | the role file's `model:`; `work` maps the tier for Claude Code (`haiku`, `sonnet`, `opus`) and passes per-tool ids |
| `scripts/skills.py`, `skills.yaml` pins, `my-skills/`, `psai adopt`, the skills cache | a stack's own skills are in its `skills/`; someone else's skill is installed through its own channel and named in `skills:` |
| `psai build --standalone`, `scripts/build.py`, `dist/` | none needed: the repo is already the package for every channel |
| `psai publish`, `scripts/publish.py` | push a commit or a `vX.Y.Z` tag |
| `psai new-stack`, `template/stack/` | `customize-harness` scaffolds a stack from its own `template/` folder |
| `psai check`, `psai eval`, `psai graph`, `psai simulate` for users | maintainer scripts in psai (`scripts/check.sh`, `evals/run.sh`) that a stack's CI runs; `customize-harness/graph.py`, an optional diagram helper |
| `install.sh` (links, plugins, the `psai` command, imports, migrations) | removed entirely; each tool's channel installs, and `scripts/link-skills.sh` links a clone for development |
| `migrations/` | none: nothing on the machine to migrate. Upgrading from 3.x is a manual one-off (below) |
| `instructions/global.md`, `instructions/owner.md`, a stack's `instructions/stack.md` | the nudge; rules for every task go in your stack's `<stack>-rules` skill, which `request-router` loads first |
| `plugins/claude`, `plugins/pi`, `plugins/omp`, `plugins/opencode` (each ran `psai context` live) | `hooks/hooks.json` (one SessionStart hook that prints the nudge), `extensions/psai.ts` (pi and omp), and opencode's `instructions` config pointing at the nudge |
| SubagentStart hook and role-mode text | the role agent's prompt says it is a role inside a workflow; the nudge says to ignore it then; pi's extension skips roles started with `PSAI_ROLE` |
| `VERSION` | the version in the manifests, which a check keeps equal |
| `LAYOUT.md` at the root (stack, framework and home layouts) | `skills/customize-harness/LAYOUT.md` (a stack's layout, shipped with the skill that uses it); psai's own layout in AGENTS.md |

## What we give up
- **A deterministic resolver.** 3.0 found every file by name with code; now the agent follows `skill:path` refs itself. A wrong ref is caught by the maintainer checks in CI, not at run time.
- **Overrides.** You can no longer replace one file of someone else's stack and be told when the original changes. You copy the workflow into your stack under your own name and own the copy.
- **Merged routing.** No cross-stack decision tree, priorities or `prefer` rules computed by code; the router matches descriptions, and a rule may name a preference.
- **The session ledger and its safety net.** Nothing records sessions, so a session that ends without a retro is not flagged later. `work` still always runs the retro at the end of a workflow.
- **Drift detection** (new unmanaged skills, global rules or memories the tools picked up). The retro still looks at what the conversation shows.
- **Pinned `requires:` between stacks** and version-range checks against the framework. A stack's README says what it needs; each channel pins or updates as it does.
- **One installer for every tool.** Each tool needs its own one-line install. In exchange there is nothing of ours to install, update or uninstall.
- **trace.sh without Python.** `trace.sh` needs python3 with PyYAML to check edges; without them it only records the node and says so.

## Upgrading from 3.x
1. In the 3.x clone, run `./install.sh --uninstall` (it keeps `~/.psai/overlay` and the stacks).
2. Your overlay becomes your stack: let `customize-harness` scaffold one at `$PSAI_STACK` and move each workflow into a `workflow-<stack>-<name>` skill (its steps, and the roles, guides and templates only it uses, go inside; shared ones into `<stack>-shared`), `instructions/owner.md` into `<stack>-rules`, and `knowledge/` as it is.
3. Install psai and your stack through your tools' channels (README).

## Delivery
Four stacked PRs, each passing `scripts/check.sh --upstream`:
1. This ADR, the removals, the native manifests and nudge files, and the runtime skills (`request-router`, `work`, `capture-knowledge`, `retro`, `sync`) rewritten without the CLI.
2. Content in skills: `customize-harness` rewritten (it scaffolds stacks and builds workflows as skills), with `LAYOUT.md`, `FORMATS.md`, the stack template and the graph helper; the router's discovery convention.
3. CI, the dev checks for workflows (refs, graph rules, simulation), the test stacks in the new layout, and the evals driver.
4. The human guide in `docs/guide/` and the consumer-install proof in every tool's channel.
