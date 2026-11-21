#!/usr/bin/env bash
# ADR 0011: turn a fork-layout home (PSAI_LINK, ~/.psai, a link to a psai clone) into a stacks-layout home:
# framework/ links the clone, the fork's user-owned files go into overlay/ (the stack nostack), .state/ moves to
# state/. The clone itself is never changed. A home that is already a folder is left alone (nothing to do).
# install.sh runs this before it sets up the home; the migrations runner then records it as done.
set -euo pipefail
link="${PSAI_LINK:-$HOME/.psai}"
[ -L "$link" ] || exit 0
clone="$(cd -P "$link" && pwd)"
[ -f "$clone/install.sh" ] && [ -f "$clone/skills/work/SKILL.md" ] || exit 0
python3 "${PSAI_REPO:-$clone}/scripts/stacks.py" migrate-fork --home "$link" --clone "$clone" $([ "${DRY_RUN:-0}" = 1 ] && echo --dry-run)
