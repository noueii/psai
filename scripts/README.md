# scripts/

Maintainer-only tooling: never shipped to users, never installed. Run from a clone of psai (or by a stack's CI, with a stack's path).
- `check.sh [--upstream] [<stack>]`: every check; `--upstream` also fails if psai ships content.
- `check.py`: the file checks `check.sh` runs (SKILL.md frontmatter, manifests, READMEs). Needs python3 with PyYAML.
- `link-skills.sh [--unlink] [--dry-run]`: links this clone's skills into `~/.claude/skills` and `~/.agents/skills` for development (it runs `skills/customize-harness/link-skills.sh`).

Example: `scripts/check.sh --upstream`.
