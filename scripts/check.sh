#!/usr/bin/env bash
# Validate the repo and test install.sh against temp HOMEs. Never touches the real HOME.
# Usage: scripts/check.sh [--discover]
#   --discover  also ask the installed tools (opencode, pi, omp) which skills they see.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
fails=0
pass() { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; fails=$((fails + 1)); }
check() { local msg="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$msg"; else fail "$msg"; fi; }

echo "frontmatter"
for md in "$ROOT"/skills/*/SKILL.md; do
  dir="$(basename "$(dirname "$md")")"
  fm="$(awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} NR>1 {print}' "$md")"
  [ -n "$fm" ] || { fail "$dir: no frontmatter"; continue; }
  name="$(printf '%s\n' "$fm" | sed -n 's/^name:[[:space:]]*//p' | tr -d '"'"'")"
  desc="$(printf '%s\n' "$fm" | sed -n 's/^description:[[:space:]]*//p' | tr -d '"'"'")"
  [ "$name" = "$dir" ] && pass "$dir: name == folder" || fail "$dir: name '$name' != folder"
  [[ "$name" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || fail "$dir: name not lowercase-hyphen"
  [ -n "$desc" ] && pass "$dir: description present" || fail "$dir: description missing"
  [ "${#desc}" -le 1024 ] || fail "$dir: description over 1024 chars"
  printf '%s\n' "$fm" | grep -q '^disable-model-invocation' && fail "$dir: disable-model-invocation set"
done
check "skills/ is flat" test -z "$(find "$ROOT/skills" -mindepth 3 -name SKILL.md)"

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT

echo "role boundaries (check-diff.sh)"
D="$ROOT/skills/task-loop/check-diff.sh"
g="$T/gitrepo"; mkdir -p "$g/src" "$g/tests"; echo a > "$g/src/app.js"
(cd "$g" && git init -q && git add . && git -c user.email=c@c -c user.name=c commit -qm init) || fail "git init"
b="$(git -C "$g" rev-parse HEAD)"
echo t > "$g/tests/a.test.js"
check "qa may add tests" bash -c "cd '$g' && '$D' qa $b"
check "reviewer may not touch tests" bash -c "cd '$g' && ! '$D' reviewer $b"
echo x >> "$g/src/app.js"
check "qa may not touch product code" bash -c "cd '$g' && ! '$D' qa $b"
check "QA_ALLOW extends qa" bash -c "cd '$g' && QA_ALLOW='^src/app\.js$' '$D' qa $b"
check "engineer may touch code" bash -c "cd '$g' && '$D' engineer $b"

# ---------- installer ----------
I="$ROOT/install.sh"
snap() { (cd "$1" && find . \( -type f -o -type l \) -print0 | sort -z | xargs -0 -I{} sh -c 'printf "%s " "{}"; if [ -L "{}" ]; then readlink "{}"; else md5sum < "{}"; fi') ; }
run() { env -u XDG_CONFIG_HOME HOME="$1" bash "$I" "${@:2}"; }

echo "install: all four tools"
h="$T/all"
mkdir -p "$h/.claude/skills" "$h/.config/opencode" "$h/.pi/agent" "$h/.omp/agent" "$h/.agents/skills/foreign"
printf 'keep me' > "$h/.claude/CLAUDE.md"
printf '# owner rules\n' > "$h/.config/opencode/AGENTS.md"
echo foreign > "$h/.agents/skills/foreign/SKILL.md"
before="$(snap "$h")"
run "$h" --dry-run > "$T/dry.out"
check "dry-run changes nothing" test "$before" = "$(snap "$h")"
check "dry-run reports actions" grep -q '^would: link' "$T/dry.out"
run "$h" > "$T/inst.out" || fail "install exited non-zero"
check "~/.harness links to repo" test "$(readlink "$h/.harness")" = "$ROOT"
for s in "$ROOT"/skills/*/; do
  n="$(basename "$s")"
  check "claude skill $n" test -f "$h/.claude/skills/$n/SKILL.md"
  check "agents skill $n" test -f "$h/.agents/skills/$n/SKILL.md"
done
check "foreign skill untouched" grep -qx foreign "$h/.agents/skills/foreign/SKILL.md"
imp='@~/.harness/instructions/global.md'
check "claude import once" test "$(grep -Fxc "$imp" "$h/.claude/CLAUDE.md")" = 1
check "claude content kept" grep -q '^keep me$' "$h/.claude/CLAUDE.md"
check "omp import once" test "$(grep -Fxc "$imp" "$h/.omp/agent/AGENTS.md")" = 1
check "pi block once" test "$(grep -c 'harness:start' "$h/.pi/agent/AGENTS.md")" = 1
check "pi block is global.md" diff <(sed -n '/harness:start/,/harness:end/p' "$h/.pi/agent/AGENTS.md" | sed '1d;$d') "$ROOT/instructions/global.md"
check "opencode block once" test "$(grep -c 'harness:start' "$h/.config/opencode/AGENTS.md")" = 1
check "opencode content kept" grep -q '^# owner rules$' "$h/.config/opencode/AGENTS.md"
check "backup of CLAUDE.md" cmp -s "$h/.claude/CLAUDE.md.harness-backup" <(printf 'keep me')
check "backup of opencode AGENTS.md" test -f "$h/.config/opencode/AGENTS.md.harness-backup"
check "no backup for files it created" test ! -e "$h/.pi/agent/AGENTS.md.harness-backup"

echo "re-run is idempotent"
after="$(snap "$h")"
run "$h" > /dev/null
check "second install changes nothing" test "$after" = "$(snap "$h")"

echo "update: refresh block, drop stale links"
sed -i 's/^## Principles$/## STALE/' "$h/.pi/agent/AGENTS.md"
ln -s "$h/.harness/skills/old-skill" "$h/.agents/skills/old-skill"
run "$h" > /dev/null
check "stale block refreshed" grep -q '^## Principles$' "$h/.pi/agent/AGENTS.md"
check "stale skill link removed" test ! -L "$h/.agents/skills/old-skill"
check "state equals fresh install" test "$after" = "$(snap "$h")"

echo "uninstall"
run "$h" --uninstall --dry-run > /dev/null
check "uninstall dry-run changes nothing" test "$after" = "$(snap "$h")"
run "$h" --uninstall > /dev/null || fail "uninstall exited non-zero"
check "~/.harness removed" test ! -e "$h/.harness"
check "no harness links left" test -z "$(find "$h/.claude/skills" "$h/.agents/skills" -maxdepth 1 -type l)"
check "CLAUDE.md content restored" grep -qx 'keep me' "$h/.claude/CLAUDE.md"
check "CLAUDE.md import gone" test "$(grep -Fc "$imp" "$h/.claude/CLAUDE.md")" = 0
check "opencode AGENTS.md restored" cmp -s "$h/.config/opencode/AGENTS.md" "$h/.config/opencode/AGENTS.md.harness-backup"
check "created pi file removed" test ! -e "$h/.pi/agent/AGENTS.md"
check "created omp file removed" test ! -e "$h/.omp/agent/AGENTS.md"
check "foreign skill survives" test -f "$h/.agents/skills/foreign/SKILL.md"

echo "only tools present"
h="$T/pionly"; mkdir -p "$h/.pi/agent"
run "$h" > /dev/null
check "no ~/.claude created" test ! -e "$h/.claude"
check "no opencode created" test ! -e "$h/.config/opencode"
check "no omp created" test ! -e "$h/.omp"
check "pi gets skills" test -f "$h/.agents/skills/task-loop/SKILL.md"
h="$T/claudeonly"; mkdir -p "$h/.claude"
run "$h" > /dev/null
check "claude-only: no ~/.agents" test ! -e "$h/.agents"
check "claude-only: CLAUDE.md created" grep -Fxq "$imp" "$h/.claude/CLAUDE.md"

echo "never clobber"
h="$T/clash"; mkdir -p "$h/.claude/skills/task-loop" "$h/.pi/agent"
echo mine > "$h/.claude/skills/task-loop/SKILL.md"
printf 'pi rules\n' > "$h/.pi/agent/CLAUDE.md"
run "$h" > /dev/null 2> "$T/clash.err"
check "existing skill dir kept" grep -qx mine "$h/.claude/skills/task-loop/SKILL.md"
check "clash reported" grep -q 'not ours' "$T/clash.err"
check "pi uses its existing CLAUDE.md" grep -q harness:start "$h/.pi/agent/CLAUDE.md"
check "pi AGENTS.md not created" test ! -e "$h/.pi/agent/AGENTS.md"
h="$T/taken"; mkdir -p "$h/.harness" "$h/.claude"
check "refuses a foreign ~/.harness" test "$(run "$h" >/dev/null 2>&1; echo $?)" = 1

# ---------- discovery (optional, uses the real tool binaries in a temp HOME) ----------
if [ "${1:-}" = "--discover" ]; then
  echo "discovery"
  h="$T/disc"; mkdir -p "$h/.claude" "$h/.config/opencode" "$h/.pi/agent" "$h/.omp/agent" "$h/w"
  run "$h" > /dev/null
  cd "$h/w" || exit 1
  if command -v opencode >/dev/null; then
    out="$(HOME="$h" XDG_CONFIG_HOME="$h/.config" XDG_DATA_HOME="$h/.d" XDG_CACHE_HOME="$h/.c" XDG_STATE_HOME="$h/.s" \
      timeout 120 opencode debug skill --pure 2>/dev/null)"
    for n in task-loop capture-knowledge sanitize-pr; do
      check "opencode sees $n once" test "$(printf '%s' "$out" | grep -c "\"name\": \"$n\"")" = 1
    done
  fi
  if command -v pi >/dev/null; then
    out="$(echo '{"type":"get_commands"}' | HOME="$h" timeout 60 pi --mode rpc --no-session --offline 2>/dev/null)"
    for n in task-loop capture-knowledge sanitize-pr; do check "pi sees $n" grep -q "skill:$n\"" <<< "$out"; done
  fi
  if command -v omp >/dev/null; then
    out="$( (echo '{"type":"get_state"}'; sleep 10) | HOME="$h" ANTHROPIC_API_KEY=dummy timeout 90 omp --mode rpc --no-session --no-title 2>/dev/null)"
    for n in task-loop capture-knowledge sanitize-pr; do check "omp sees $n" grep -q "skill:$n\"" <<< "$out"; done
    check "omp loads global.md via import" grep -q 'Escalation policy' <<< "$out"
  fi
  cd "$ROOT" || exit 1
fi

echo
if [ "$fails" = 0 ]; then echo "check: all passed"; else echo "check: $fails failed"; exit 1; fi
