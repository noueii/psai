# scripts/

- `check.sh`: L0 (structure, LAYOUT, frontmatter, paths, graph shape, README diagrams, check-diff), L1 (installer in temp HOMEs) and L2 (simulate). `--quick` skips L1; `--discover` asks the real tools what they see.
- `simulate.py <root>`: walks each workflow with the scripted outcomes in `workflows/<name>.cases.yaml`, and the routing tree with `ROUTING.cases.yaml`.
- `graph.py <root>`: Mermaid (`--mermaid <wf>`) or SVG (`--svg <wf>`), and keeps README diagrams fresh (`--update-readme`, `--check-readme`).
- `harness.py`: shared loading and validation, used by the three above. `harness.py context <root>` prints the always-on nudge that every plugin injects.
- `skills.py`, run as `harness.py skills [list|check|brief|packs|adopt]`: the live skill registry. It scans psai's skills/, my-skills/, the skills.yaml packs, each tool's user skill folders and the current project's, and says which tools see each skill and which are unmanaged. `check` fails on a required skill that resolves nowhere; `brief <role> [<step>]` prints a role agent's skill list; `adopt <name>` is what `install.sh --adopt` runs.
- `test-plugins.sh`: proves without AI or network that each tool's plugin puts the nudge into the session (run by check.sh).
