#!/usr/bin/env bash
# legacy: the base folder was ~/.harness before the rename to ~/.psai. Remove that link, but only when it is a link
# to a psai clone and isn't the current base link. install.sh has already relinked what went through it.
set -euo pipefail
old="$HOME/.harness"
[ "${PSAI_LINK:-$HOME/.psai}" = "$old" ] && exit 0
is_clone() { [ -f "$1/install.sh" ] && [ -f "$1/instructions/global.md" ] && [ -f "$1/skills/capture-knowledge/SKILL.md" ]; }
if [ -L "$old" ] && is_clone "$old"; then
  if [ "${DRY_RUN:-0}" = 1 ]; then echo "would: unlink old base $old (now ${PSAI_LINK:-$HOME/.psai})"
  else echo "unlink old base $old (now ${PSAI_LINK:-$HOME/.psai})"; rm -f "$old"; fi
fi
