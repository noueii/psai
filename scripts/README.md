# scripts/

Maintainer-only tooling: never shipped to users, never installed. Run from a clone of psai (or by a stack's CI, with a stack's path).
- `check.sh [--upstream] [<stack> [--with <stack>]]`: every check; `--upstream` also fails if psai ships content. CI runs it on every PR (`.github/workflows/check.yml`), and a stack's CI runs it on the stack (customize-harness's template).
- `check.py`: the file checks `check.sh` runs: SKILL.md frontmatter, manifests, READMEs, skill names, and each workflow skill (with `workflows.py`). Needs python3 with PyYAML.
- `workflows.py`: workflow checks: refs resolve, every node reachable and able to end, every automatic loop limited, and the simulator, which walks `evals/cases/<workflow skill>.yaml`.
- `prove-tutorial.sh [--keep]`: the consumer-install proof. It runs every `sh` block of `docs/guide/tutorial.md`, as written, in a temp HOME: psai (this clone's HEAD) and the tutorial's stack are served over smart HTTP on localhost (`git-http.py`), and each tool's install channel installs them. A fake model (`fake-model.py`) then records what Claude Code, pi, omp and opencode send, to show the nudge and every skill reach the model, and that the update in step 8 arrives through each channel. It needs the four tools and, once, the network for `npx skills`. Run it after changing the tutorial, the manifests, the nudge files or the template.
- `link-skills.sh [--unlink] [--dry-run]`: links this clone's skills into `~/.claude/skills` and `~/.agents/skills` for development (it runs `skills/customize-harness/link-skills.sh`).

Example: `scripts/check.sh --upstream`.
