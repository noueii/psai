#!/usr/bin/env bash
# Install, refresh or remove the harness for Claude Code, opencode, pi and omp.
# Usage: ./install.sh [--dry-run] [--uninstall]
# Idempotent. Touches only its own links, plugin files and plugin registration. One injection path per tool:
# a plugin that injects the live psai nudge (scripts/harness.py context). v1's import lines and marked blocks
# are removed on upgrade.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
H="$HOME/.harness"
IMPORT='@~/.harness/instructions/global.md'          # v1/early v2 import lines, removed on upgrade
OWNER_IMPORT='@~/.harness/instructions/owner.md'
STUB_MARK='// psai: managed by install.sh'
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

remove_import() {
  local f="$1"
  [ -e "$f" ] && grep -Fxq -e "$IMPORT" -e "$OWNER_IMPORT" "$f" || return 0
  grep -Fxv -e "$IMPORT" -e "$OWNER_IMPORT" "$f" > "$TMP" || true
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


# ---------- plugins: the one injection path per tool ----------
ours_link() { [ -L "$1" ] && case "$(readlink "$1")" in "$H"/*|"$REPO"/*) true ;; *) false ;; esac; }

link_file() { # target source
  local t="$1" src="$2"
  if ours_link "$t"; then
    [ "$(readlink "$t")" = "$src" ] && return
    say "relink $t"; do_ ln -sfn "$src" "$t"
  elif [ -e "$t" ] || [ -L "$t" ]; then
    echo "skip: $t exists and is not ours" >&2
  else
    [ -d "$(dirname "$t")" ] || { say "mkdir $(dirname "$t")"; do_ mkdir -p "$(dirname "$t")"; }
    say "link $t -> $src"; do_ ln -s "$src" "$t"
  fi
}

unlink_file() { if ours_link "$1"; then say "unlink $1"; do_ rm -f "$1"; fi; }

OC_STUB="$CFG/opencode/plugin/psai.js"   # opencode loads only real files from plugin/, so a stub imports the live one
install_opencode_stub() {
  if [ -e "$OC_STUB" ] && ! grep -Fxq "$STUB_MARK" "$OC_STUB"; then echo "skip: $OC_STUB exists and is not ours" >&2; return; fi
  printf '%s\nexport { Psai } from "%s/plugins/opencode/psai.js";\n' "$STUB_MARK" "$H" > "$TMP"
  write_if_changed "$OC_STUB" "$TMP"
}
remove_opencode_stub() {
  if [ -f "$OC_STUB" ] && grep -Fxq "$STUB_MARK" "$OC_STUB"; then say "remove $OC_STUB"; do_ rm -f "$OC_STUB"; fi
}

claude_state() { # "installed" when the psai marketplace points at $H and psai@psai is enabled; "other"; "absent"
  python3 - "$HOME/.claude/settings.json" "$H" <<'PY'
import json, sys
try:
    s = json.load(open(sys.argv[1]))
except Exception:
    s = {}
src = ((s.get("extraKnownMarketplaces") or {}).get("psai") or {}).get("source") or {}
ok = src.get("path") == sys.argv[2] and (s.get("enabledPlugins") or {}).get("psai@psai") is True
print("installed" if ok else ("other" if src or "psai@psai" in (s.get("enabledPlugins") or {}) else "absent"))
PY
}

install_claude_plugin() {
  local st; st="$(claude_state)"
  [ "$st" = installed ] && return
  if ! command -v claude >/dev/null; then
    echo "skip: claude CLI not found; later run: claude plugin marketplace add $H && claude plugin install psai@psai" >&2
    return
  fi
  [ -f "$HOME/.claude/settings.json" ] && backup "$HOME/.claude/settings.json"
  if [ "$st" = other ]; then say "claude: re-point marketplace psai to $H"; do_ claude plugin marketplace remove psai >/dev/null 2>&1 || true; fi
  say "claude: plugin marketplace add $H"; do_ claude plugin marketplace add "$H" >/dev/null
  say "claude: plugin install psai@psai"; do_ claude plugin install psai@psai --scope user >/dev/null
}

uninstall_claude_plugin() {
  [ "$(claude_state)" = absent ] && return
  command -v claude >/dev/null || { echo "skip: claude CLI not found; remove psai@psai with /plugin" >&2; return; }
  say "claude: plugin uninstall psai@psai"; do_ claude plugin uninstall psai@psai --scope user >/dev/null 2>&1 || true
  say "claude: plugin marketplace remove psai"; do_ claude plugin marketplace remove psai >/dev/null 2>&1 || true
}

remove_legacy() { # v1 and early v2 wrote import lines and inlined blocks; the plugins replace them
  remove_import "$HOME/.claude/CLAUDE.md"
  remove_import "$HOME/.omp/agent/AGENTS.md"
  for f in "$HOME/.pi/agent/AGENTS.md" "$HOME/.pi/agent/AGENTS.MD" "$HOME/.pi/agent/CLAUDE.md" "$HOME/.pi/agent/CLAUDE.MD" "$CFG/opencode/AGENTS.md"; do
    remove_block "$f"
  done
}

install() {
  link_harness
  link_skills
  remove_legacy
  has_claude && install_claude_plugin
  has_pi && link_file "$HOME/.pi/agent/extensions/psai.ts" "$H/plugins/pi/psai.ts"
  has_omp && link_file "$HOME/.omp/agent/extensions/psai.ts" "$H/plugins/omp/psai.ts"
  has_opencode && install_opencode_stub
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
  remove_legacy
  [ -d "$HOME/.claude" ] && uninstall_claude_plugin
  unlink_file "$HOME/.pi/agent/extensions/psai.ts"
  unlink_file "$HOME/.omp/agent/extensions/psai.ts"
  remove_opencode_stub
  if [ -L "$H" ] && [ "$(readlink "$H")" = "$REPO" ]; then
    say "unlink $H"
    do_ rm -f "$H"
  fi
  echo "harness: uninstall done$([ "$DRY" = 1 ] && echo ' (dry run)'). Backups (*.harness-backup) were kept."
}

"$MODE"
