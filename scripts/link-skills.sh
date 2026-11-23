#!/usr/bin/env bash
# Development install of psai itself: link this repo's skills into ~/.claude/skills and ~/.agents/skills.
# Same options as the script it runs (--unlink, --dry-run). Stacks use that script directly.
exec "$(dirname "$0")/../skills/customize-harness/link-skills.sh" "$(cd "$(dirname "$0")/.." && pwd -P)" "$@"
