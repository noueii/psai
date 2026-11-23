#!/usr/bin/env bash
# Development install: link every skill of a skills repo (psai, or a stack) into the tools' skill folders, so a
# `git pull` or an edit in the clone is live at once. Each entry is a symlink into the repo.
# Usage: link-skills.sh [<repo>] [--unlink] [--dry-run]     (<repo> defaults to the current git repo)
#   ~/.claude/skills: Claude Code (opencode reads it too)
#   ~/.agents/skills: pi, omp, opencode, Codex and other Agent Skills tools
# It never replaces a folder or a link that isn't its own, and --unlink removes only links into <repo>.
set -euo pipefail
repo=""; mode=link; dry=0
for a in "$@"; do
  case "$a" in --unlink) mode=unlink ;; --dry-run) dry=1 ;; -*) echo "unknown option: $a" >&2; exit 2 ;; *) repo="$a" ;; esac
done
repo="$(cd "${repo:-$(git rev-parse --show-toplevel)}" && pwd -P)"
[ -d "$repo/skills" ] || { echo "no skills/ in $repo" >&2; exit 1; }
run() { if [ "$dry" = 1 ]; then echo "would: $*"; else "$@"; fi; }
for dest in "$HOME/.claude/skills" "$HOME/.agents/skills"; do
  case "$(readlink -f "$dest" 2>/dev/null || true)" in "$repo"|"$repo"/*) echo "skip $dest: it points into $repo" >&2; continue ;; esac
  if [ "$mode" = unlink ]; then
    for t in "$dest"/*; do
      [ -L "$t" ] && case "$(readlink "$t")" in "$repo"/*) run rm "$t"; echo "unlinked $(basename "$t") ($dest)" ;; esac
    done
    continue
  fi
  run mkdir -p "$dest"
  for md in "$repo"/skills/*/SKILL.md; do
    src="$(dirname "$md")"; t="$dest/$(basename "$src")"
    if [ -L "$t" ] && [ "$(readlink "$t")" = "$src" ]; then continue; fi
    if [ -e "$t" ] || [ -L "$t" ]; then
      case "$(readlink "$t" 2>/dev/null || true)" in
        "$repo"/*) ;;   # a stale link of ours: replace it
        *) echo "skip $t: it exists and isn't a link into $repo" >&2; continue ;;
      esac
    fi
    run ln -sfn "$src" "$t"; echo "linked $(basename "$src") -> $src ($dest)"
  done
done
