#!/usr/bin/env bash
# Install, refresh or remove the harness for Claude Code, opencode, pi and omp.
# Usage: ./install.sh [--dry-run] [--uninstall]
# Idempotent. Touches only its own links, its import line and its marked block.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
H="$HOME/.harness"
IMPORT='@~/.harness/instructions/global.md'
START='<!-- harness:start -->'
END='<!-- harness:end -->'
CFG="${XDG_CONFIG_HOME:-$HOME/.config}"

DRY=0
MODE=install
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --uninstall) MODE=uninstall ;;
    -h|--help) sed -n '2,4p' "$0" | sed 's/^# //'; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

say() { if [ "$DRY" = 1 ]; then echo "would: $*"; else echo "$*"; fi; }
do_() { [ "$DRY" = 1 ] || "$@"; }

# A tool counts as present when its config folder exists.
has_claude() { [ -d "$HOME/.claude" ]; }
has_opencode() { [ -d "$CFG/opencode" ]; }
has_pi() { [ -d "$HOME/.pi/agent" ]; }
has_omp() { [ -d "$HOME/.omp/agent" ]; }

# pi reads the first of AGENTS.md / CLAUDE.md that exists; write to that one.
pi_file() {
  local d="$HOME/.pi/agent"
  for f in AGENTS.md AGENTS.MD CLAUDE.md CLAUDE.MD; do
    [ -e "$d/$f" ] && { echo "$d/$f"; return; }
  done
  echo "$d/AGENTS.md"
}

backup() { # before the first edit of an existing file (one with no harness content yet)
  local f="$1"
  if [ -e "$f" ] && [ ! -e "$f.harness-backup" ] \
    && ! grep -Fxq -e "$IMPORT" -e "$START" "$f"; then
    say "backup $f -> $f.harness-backup"
    do_ cp -p "$f" "$f.harness-backup"
  fi
}

write_if_changed() { # file newcontent-file
  local f="$1" new="$2"
  if [ -e "$f" ] && cmp -s "$f" "$new"; then return; fi
  backup "$f"
  if [ -e "$f" ]; then say "update $f"; else say "create $f"; fi
  if [ "$DRY" = 0 ]; then
    mkdir -p "$(dirname "$f")"
    cat "$new" > "$f" # keeps symlinks and permissions intact
  fi
}

# Remove our content; delete the file only if we created it and it is now empty.
finish_removal() {
  local f="$1" new="$2"
  if cmp -s "$f" "$new"; then return; fi
  if [ ! -e "$f.harness-backup" ] && ! grep -q '[^[:space:]]' "$new"; then
    say "remove $f (created by harness, now empty)"
    do_ rm -f "$f"
  else
    say "update $f"
    [ "$DRY" = 1 ] || cat "$new" > "$f"
  fi
}

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

add_import() {
  local f="$1"
  if [ -e "$f" ] && grep -Fxq "$IMPORT" "$f"; then return; fi
  if [ -s "$f" ]; then
    cat "$f" > "$TMP"
    [ -n "$(tail -c 1 "$f")" ] && echo >> "$TMP"
  else
    : > "$TMP"
  fi
  echo "$IMPORT" >> "$TMP"
  write_if_changed "$f" "$TMP"
}

remove_import() {
  local f="$1"
  [ -e "$f" ] && grep -Fxq "$IMPORT" "$f" || return 0
  grep -Fxv "$IMPORT" "$f" > "$TMP" || true
  finish_removal "$f" "$TMP"
}

# Strip our block (and the blank line we put before it) from file $1 to stdout.
strip_block() {
  awk -v s="$START" -v e="$END" '
    $0 == s { inb = 1; held = 0; next }
    inb { if ($0 == e) inb = 0; next }
    { if (held) print ""; held = 0 }
    $0 == "" { held = 1; next }
    { print }
    END { if (held && !inb) print "" }
  ' "$1"
}

upsert_block() {
  local f="$1"
  if [ -e "$f" ]; then strip_block "$f" > "$TMP"; else : > "$TMP"; fi
  [ -s "$TMP" ] && echo >> "$TMP"
  { echo "$START"; cat "$REPO/instructions/global.md"; echo "$END"; } >> "$TMP"
  write_if_changed "$f" "$TMP"
}

remove_block() {
  local f="$1"
  [ -e "$f" ] && grep -Fxq "$START" "$f" || return 0
  strip_block "$f" > "$TMP"
  finish_removal "$f" "$TMP"
}

# Is $1 a symlink to one of our skills?
ours() {
  [ -L "$1" ] || return 1
  case "$(readlink "$1")" in "$H"/skills/*|"$REPO"/skills/*) return 0 ;; esac
  return 1
}

skill_dests() {
  has_claude && echo "$HOME/.claude/skills"
  if has_pi || has_omp || has_opencode; then echo "$HOME/.agents/skills"; fi
  return 0
}

link_harness() {
  if [ -L "$H" ]; then
    [ "$(readlink "$H")" = "$REPO" ] && return
    echo "error: $H points to $(readlink "$H"), not $REPO. Remove it or run install.sh from that clone." >&2
    exit 1
  elif [ -e "$H" ]; then
    echo "error: $H exists and is not a link. Move it away first." >&2
    exit 1
  fi
  say "link $H -> $REPO"
  do_ ln -s "$REPO" "$H"
}

link_skills() {
  local dest name target
  while IFS= read -r dest; do
    [ -n "$dest" ] || continue
    [ -d "$dest" ] || { say "mkdir $dest"; do_ mkdir -p "$dest"; }
    for md in "$REPO"/skills/*/SKILL.md; do
      name="$(basename "$(dirname "$md")")"
      target="$dest/$name"
      if ours "$target"; then
        [ "$(readlink "$target")" = "$H/skills/$name" ] && continue
        say "relink $target"
        do_ ln -sfn "$H/skills/$name" "$target"
      elif [ -e "$target" ] || [ -L "$target" ]; then
        echo "skip: $target exists and is not ours" >&2
      else
        say "link $target -> $H/skills/$name"
        do_ ln -s "$H/skills/$name" "$target"
      fi
    done
    # Drop our links to skills that no longer exist.
    for target in "$dest"/*; do
      if ours "$target" && [ ! -e "$REPO/skills/$(basename "$target")/SKILL.md" ]; then
        say "unlink stale $target"
        do_ rm -f "$target"
      fi
    done
  done < <(skill_dests)
}

install() {
  link_harness
  link_skills
  has_claude && add_import "$HOME/.claude/CLAUDE.md"
  has_omp && add_import "$HOME/.omp/agent/AGENTS.md"
  has_pi && upsert_block "$(pi_file)"
  has_opencode && upsert_block "$CFG/opencode/AGENTS.md"
  echo "harness: install done$([ "$DRY" = 1 ] && echo ' (dry run)')"
}

uninstall() {
  local target
  for dest in "$HOME/.claude/skills" "$HOME/.agents/skills"; do
    [ -d "$dest" ] || continue
    for target in "$dest"/*; do
      if ours "$target"; then say "unlink $target"; do_ rm -f "$target"; fi
    done
  done
  remove_import "$HOME/.claude/CLAUDE.md"
  remove_import "$HOME/.omp/agent/AGENTS.md"
  for f in "$HOME/.pi/agent/AGENTS.md" "$HOME/.pi/agent/AGENTS.MD" "$HOME/.pi/agent/CLAUDE.md" "$HOME/.pi/agent/CLAUDE.MD" "$CFG/opencode/AGENTS.md"; do
    remove_block "$f"
  done
  if [ -L "$H" ] && [ "$(readlink "$H")" = "$REPO" ]; then
    say "unlink $H"
    do_ rm -f "$H"
  fi
  echo "harness: uninstall done$([ "$DRY" = 1 ] && echo ' (dry run)'). Backups (*.harness-backup) were kept."
}

"$MODE"
