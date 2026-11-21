#!/usr/bin/env bash
# Install, refresh or remove psai for Claude Code, opencode, pi and omp.
# Usage: ./install.sh [--dry-run] [--uninstall] [--adopt <skill>]    (PSAI_HOME overrides the link path, default ~/.psai)
# Idempotent. Touches only its own links, plugin files, README-psai.md and plugin registration. Links psai's skills/,
# your my-skills/ and the pinned skills.yaml packs (fetched into the git-ignored .skills-cache/) into ~/.claude/skills
# and ~/.agents/skills. --adopt brings one unmanaged skill from a tool folder under psai. One injection path per tool:
# a plugin that injects the live psai nudge (scripts/harness.py context). On upgrade it removes v1's import lines
# and marked blocks, and the old base link if it points to a psai clone.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
H="${PSAI_HOME:-$HOME/.psai}"
H="${H%/}"
OLD_H="$HOME/.harness"                                # legacy base link (before the rename), removed on upgrade
IMPORT='@~/.harness/instructions/global.md'          # legacy: v1/early v2 import lines, removed on upgrade
OWNER_IMPORT='@~/.harness/instructions/owner.md'     # legacy
STUB_MARK='// psai: managed by install.sh'
START='<!-- harness:start -->'
END='<!-- harness:end -->'
CFG="${XDG_CONFIG_HOME:-$HOME/.config}"

DRY=0
MODE=install
ADOPT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --uninstall) MODE=uninstall ;;
    --adopt) [ -n "${2:-}" ] || { echo "--adopt needs a skill name" >&2; exit 2; }; ADOPT="$2"; shift ;;
    -h|--help) sed -n '2,5p' "$0" | sed 's/^# //'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
CACHE="$REPO/.skills-cache"
README_MARK='<!-- psai: managed by install.sh -->'

say() { if [ "$DRY" = 1 ]; then echo "would: $*"; else echo "$*"; fi; }
do_() { [ "$DRY" = 1 ] || "$@"; }

# A tool counts as present when its config folder exists.
has_claude() { [ -d "$HOME/.claude" ]; }
has_opencode() { [ -d "$CFG/opencode" ]; }
has_pi() { [ -d "$HOME/.pi/agent" ]; }
has_omp() { [ -d "$HOME/.omp/agent" ]; }

# Backups are *.psai-backup; *.harness-backup is the name older versions used.
has_backup() { [ -e "$1.psai-backup" ] || [ -e "$1.harness-backup" ]; }

backup() { # before the first edit of an existing file (one with no psai content yet)
  local f="$1"
  if [ -e "$f" ] && ! has_backup "$f" \
    && ! grep -Fxq -e "$IMPORT" -e "$START" "$f"; then
    say "backup $f -> $f.psai-backup"
    do_ cp -p "$f" "$f.psai-backup"
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
  if ! has_backup "$f" && ! grep -q '[^[:space:]]' "$new"; then
    say "remove $f (created by psai, now empty)"
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

# Is $1 a psai clone? (v1 and v2 both ship these files)
is_clone() { [ -f "$1/install.sh" ] && [ -f "$1/instructions/global.md" ] && [ -f "$1/skills/capture-knowledge/SKILL.md" ]; }

# Links into the old base path are ours when it is a link to a psai clone, or gone; never when it is anything else.
OLD_OURS=0
if [ "$OLD_H" != "$H" ]; then
  if [ -L "$OLD_H" ] && is_clone "$OLD_H"; then OLD_OURS=1
  elif [ ! -e "$OLD_H" ] && [ ! -L "$OLD_H" ]; then OLD_OURS=1; fi
fi
under_ours() { # path-prefix test: is $1 inside $H, the repo or (when ours) the old base path?
  case "$1" in "$H"/*|"$REPO"/*) return 0 ;; esac
  [ "$OLD_OURS" = 1 ] && case "$1" in "$OLD_H"/*) return 0 ;; esac
  return 1
}

# Is $1 a symlink to one of our skills (psai's, my-skills/ or a fetched pack)?
ours() {
  [ -L "$1" ] || return 1
  under_ours "$(readlink "$1")"
}

skill_dests() {
  has_claude && echo "$HOME/.claude/skills"
  if has_pi || has_omp || has_opencode; then echo "$HOME/.agents/skills"; fi
  return 0
}

link_base() {
  if [ -d "$H" ] && [ ! -L "$H" ] && [ "$(cd "$H" && pwd -P)" = "$REPO" ]; then return; fi   # PSAI_HOME is the clone itself
  if [ -L "$H" ]; then
    [ "$(readlink "$H")" = "$REPO" ] && return
    echo "error: $H points to $(readlink "$H"), not $REPO. Remove it or run install.sh from that clone." >&2
    exit 1
  elif [ -e "$H" ]; then
    echo "error: $H exists and is not a link. Move it away first." >&2
    exit 1
  fi
  [ -d "$(dirname "$H")" ] || { say "mkdir $(dirname "$H")"; do_ mkdir -p "$(dirname "$H")"; }
  say "link $H -> $REPO"
  do_ ln -s "$REPO" "$H"
}

remove_old_base() { # the pre-rename base link, only if it is a link to a psai clone
  if [ "$OLD_H" != "$H" ] && [ -L "$OLD_H" ] && is_clone "$OLD_H"; then
    say "unlink old base $OLD_H (now $H)"
    do_ rm -f "$OLD_H"
  fi
}

# ---------- skills ----------
skills_py() { python3 "$REPO/scripts/harness.py" skills --root "$REPO" "$@"; }

resolve_ref() { # clone ref -> commit, only for a tag or a commit (a branch is not pinned)
  local c="$1" ref="$2"
  git -C "$c" rev-parse -q --verify "refs/tags/$ref^{commit}" 2>/dev/null && return
  [[ "$ref" =~ ^[0-9a-f]{7,40}$ ]] && git -C "$c" rev-parse -q --verify "$ref^{commit}" 2>/dev/null
}

# Fetch each pinned skills.yaml entry into .skills-cache/<name>, checked out at its ref. Network only when the
# cache is missing, points elsewhere, or doesn't have the ref yet.
fetch_packs() {
  local name url path ref c have want
  while IFS=$'\t' read -r name url path ref; do
    [ -n "$name" ] || continue
    c="$CACHE/$name"
    if [ -d "$c/.git" ] && [ "$(git -C "$c" config remote.origin.url)" = "$url" ]; then
      want="$(resolve_ref "$c" "$ref" || true)"
      have="$(git -C "$c" rev-parse -q --verify HEAD 2>/dev/null || true)"
      [ -n "$want" ] && [ "$want" = "$have" ] && continue
      if [ -z "$want" ]; then
        say "fetch $name ($url @ $ref)"; [ "$DRY" = 1 ] && continue
        git -C "$c" fetch -q --tags origin 2>/dev/null || true
        want="$(resolve_ref "$c" "$ref" || true)"
      else
        say "check out $name @ $ref"; [ "$DRY" = 1 ] && continue
      fi
    else
      say "fetch $name ($url @ $ref) -> $c"; [ "$DRY" = 1 ] && continue
      rm -rf "$c"; mkdir -p "$CACHE"
      if ! git clone -q --no-checkout "$url" "$c" 2>/dev/null; then echo "skip: can't fetch $name from $url" >&2; rm -rf "$c"; continue; fi
      want="$(resolve_ref "$c" "$ref" || true)"
    fi
    if [ -z "$want" ]; then echo "skip: $name: ref $ref is not a tag or commit in $url" >&2; continue; fi
    git -C "$c" -c advice.detachedHead=false checkout -q --detach "$want"
    [ -f "$c/$path/SKILL.md" ] || echo "skip: $name: no $path/SKILL.md in $url @ $ref" >&2
  done < <(skills_py packs)
}

# name<TAB>link target for every skill psai links: skills/, then my-skills/, then fetched packs. The first name wins.
skill_sources() {
  local md name path seen=" "
  for md in "$REPO"/skills/*/SKILL.md; do
    name="$(basename "$(dirname "$md")")"; seen+="$name "; printf '%s\t%s\n' "$name" "$H/skills/$name"
  done
  for md in "$REPO"/my-skills/*/SKILL.md; do
    [ -f "$md" ] || continue
    name="$(basename "$(dirname "$md")")"
    case "$seen" in *" $name "*) echo "skip: my-skills/$name clashes with psai's skills/$name; rename yours" >&2; continue ;; esac
    seen+="$name "; printf '%s\t%s\n' "$name" "$H/my-skills/$name"
  done
  while IFS=$'\t' read -r name _ path _; do
    [ -n "$name" ] && [ -f "$CACHE/$name/$path/SKILL.md" ] || continue
    case "$seen" in *" $name "*) echo "skip: skills.yaml entry $name clashes with another skill" >&2; continue ;; esac
    path="${path#./}"; path="${path%/}"; [ "$path" = . ] && path=""
    seen+="$name "; printf '%s\t%s\n' "$name" "$H/.skills-cache/$name${path:+/$path}"
  done < <(skills_py packs 2>/dev/null)
  return 0
}

readme_text() {
  cat <<EOT
$README_MARK
# Skills in this folder and psai

psai links three kinds of skills here: its own (\`$H/skills/\`), yours (\`$H/my-skills/\`) and other people's,
pinned in \`$H/skills.yaml\` and fetched into \`$H/.skills-cache/\`. Links into $H are psai's: edit the source,
not the link. Tools ignore this loose file.

Anything else here is unmanaged. psai lists it (\`python3 $H/scripts/harness.py skills --unmanaged\`) but never
moves or blocks it. To bring one under psai, run \`$H/install.sh --adopt <name>\`: your own skill moves into
my-skills/, a skill from a pack becomes a pinned skills.yaml entry. Skills another tool manages go in
skills.yaml's \`ignore:\` list.

To add or change a skill, use the customize-harness skill.
EOT
}

drop_readme() { # dest
  local f="$1/README-psai.md"
  if [ -e "$f" ] && ! grep -Fxq "$README_MARK" "$f"; then echo "skip: $f exists and is not ours" >&2; return; fi
  readme_text > "$TMP"
  [ -e "$f" ] && cmp -s "$f" "$TMP" && return
  say "$([ -e "$f" ] && echo update || echo create) $f"
  [ "$DRY" = 1 ] || cat "$TMP" > "$f"
}

remove_readme() {
  local f="$1/README-psai.md"
  if [ -f "$f" ] && grep -Fxq "$README_MARK" "$f"; then say "remove $f"; do_ rm -f "$f"; fi
}

link_skills() {
  local dest name src target srcs
  srcs="$(skill_sources)"
  while IFS= read -r dest; do
    [ -n "$dest" ] || continue
    [ -d "$dest" ] || { say "mkdir $dest"; do_ mkdir -p "$dest"; }
    while IFS=$'\t' read -r name src; do
      [ -n "$name" ] || continue
      target="$dest/$name"
      if ours "$target"; then
        [ "$(readlink "$target")" = "$src" ] && continue
        say "relink $target"
        do_ ln -sfn "$src" "$target"
      elif [ -e "$target" ] || [ -L "$target" ]; then
        echo "skip: $target exists and is not ours" >&2
      else
        say "link $target -> $src"
        do_ ln -s "$src" "$target"
      fi
    done <<< "$srcs"
    # Drop our links to skills that no longer exist.
    for target in "$dest"/*; do
      if ours "$target" && ! printf '%s\n' "$srcs" | cut -f1 | grep -Fxq "$(basename "$target")"; then
        say "unlink stale $target"
        do_ rm -f "$target"
      fi
    done
    drop_readme "$dest"
  done < <(skill_dests)
}


# ---------- plugins: the one injection path per tool ----------
ours_link() { [ -L "$1" ] && under_ours "$(readlink "$1")"; }

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
  link_base
  if [ -n "$ADOPT" ]; then
    skills_py adopt "$ADOPT" $([ "$DRY" = 1 ] && echo --dry-run) || exit 1
  fi
  fetch_packs
  link_skills
  remove_legacy
  remove_old_base
  has_claude && install_claude_plugin
  has_pi && link_file "$HOME/.pi/agent/extensions/psai.ts" "$H/plugins/pi/psai.ts"
  has_omp && link_file "$HOME/.omp/agent/extensions/psai.ts" "$H/plugins/omp/psai.ts"
  has_opencode && install_opencode_stub
  echo "psai: install done$([ "$DRY" = 1 ] && echo ' (dry run)')"
}

uninstall() {
  local target
  for dest in "$HOME/.claude/skills" "$HOME/.agents/skills"; do
    [ -d "$dest" ] || continue
    for target in "$dest"/*; do
      if ours "$target"; then say "unlink $target"; do_ rm -f "$target"; fi
    done
    remove_readme "$dest"
  done
  remove_legacy
  [ -d "$HOME/.claude" ] && uninstall_claude_plugin
  unlink_file "$HOME/.pi/agent/extensions/psai.ts"
  unlink_file "$HOME/.omp/agent/extensions/psai.ts"
  remove_opencode_stub
  remove_old_base
  if [ -L "$H" ] && [ "$(readlink "$H")" = "$REPO" ]; then
    say "unlink $H"
    do_ rm -f "$H"
  fi
  echo "psai: uninstall done$([ "$DRY" = 1 ] && echo ' (dry run)'). Backups (*.psai-backup) were kept."
}

"$MODE"
