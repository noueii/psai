# scripts/

- `check.sh`: L0 (structure, LAYOUT, frontmatter, paths, graph shape, README diagrams, check-diff), L1 (installer in temp HOMEs) and L2 (simulate). `--quick` skips L1; `--discover` asks the real tools what they see.
- `simulate.py <root>`: walks each workflow with the scripted outcomes in `workflows/<name>.cases.yaml`, and the routing tree with `ROUTING.cases.yaml`.
- `graph.py <root>`: Mermaid (`--mermaid <wf>`) or SVG (`--svg <wf>`), and keeps README diagrams fresh (`--update-readme`, `--check-readme`).
- `harness.py`: shared loading and validation, used by the three above. `harness.py context <root>` prints the always-on nudge that every plugin injects.
- `test-plugins.sh`: proves without AI or network that each tool's plugin puts the nudge into the session (run by check.sh).
