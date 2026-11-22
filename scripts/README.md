# scripts/

- `check.sh`: L0 (structure, LAYOUT, frontmatter, paths, graph shape, README diagrams, check-diff), L1 (installer in temp HOMEs) and L2 (simulate). `--quick` skips L1; `--discover` asks the real tools what they see.
- `simulate.py <root>`: walks each workflow with the scripted outcomes in `workflows/<name>.cases.yaml`, and the routing tree with `ROUTING.cases.yaml`.
- `graph.py <root>`: Mermaid (`--mermaid <wf>`) or SVG (`--svg <wf>`), and keeps README diagrams fresh (`--update-readme`, `--check-readme`).
- `harness.py`: shared loading and validation, used by the three above. `harness.py context <root>` prints the always-on nudge that every plugin injects.
- `skills.py`, run as `harness.py skills [list|check|brief|packs|adopt]`: the live skill registry. It scans psai's skills/, my-skills/, the skills.yaml packs, each tool's user skill folders and the current project's, and says which tools see each skill and which are unmanaged. `check` fails on a required skill that resolves nowhere; `brief <role> [<step>]` prints a role agent's skill list; `adopt <name>` is what `install.sh --adopt` runs.
- `resolve.py`: `psai resolve`, the resolution API (ADR 0011): finds a workflow, role, step, guide, template, skill, knowledge or any file by `[stack:]name` across the framework, the installed stacks and the overlay `nostack`; validates `stack.yaml` against `schemas/stack.schema.json`. A home with no `framework/` folder (today's fork clone) is one stack, `nostack`. `test-resolve.sh` tests it (run by check.sh).
- `stacks.py`: the home (ADR 0011): creates the overlay, converts a fork-layout home (migration 0002), and lists the skills and skills.yaml packs install.sh links, from the framework, the overlay and each installed stack.
- `engine.py`: `psai route` (routing trees and workflows), `psai node` (a node's resolved files and skills), `psai trace` and `psai check-diff` (the work skill's two scripts): the engine's lookups, so skills never build paths.
- `psai.py`: the one `psai` command (install.sh links it as `~/.local/bin/psai`): install, update, status, doctor, sync, retro, adopt, skills, ledger, check, context, graph, simulate, resolve. The other scripts stay as its implementations.
- `ledger.py`: the local session ledger in `.state/sessions/` (plugins write it at session start and end; trace.sh, retro and sync update it).
- `sync.py`: the sync machinery: the deterministic out-of-sync check, the ff-only update, drift fingerprints, the stage worktree, the one-PR builder, migrations.
- `retro.py`: `gather` prints a run's facts for the retro skill; `finish` saves its report and builds the PR.
- `test-plugins.sh`: proves without AI or network that each tool's plugin puts the nudge into the session (run by check.sh).
