#!/usr/bin/env bash
# Validate the harness (L0), its installer against temp HOMEs (L1) and its workflows by simulation (L2).
# Never touches the real HOME.
# Usage: scripts/check.sh [--quick] [--discover] [<extra-root>...]
#   --quick     skip the installer tests (what customize-harness runs while editing)
#   --discover  also ask the installed tools (opencode, pi, omp) which skills they see
#   <extra-root> also validate another harness root (L0 content checks + L2)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
FIX="$ROOT/evals/fixtures/harness-content"
QUICK=0; DISCOVER=0; EXTRA=()
for a in "$@"; do
  case "$a" in --quick) QUICK=1 ;; --discover) DISCOVER=1 ;; *) EXTRA+=("$a") ;; esac
done
fails=0
pass() { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; fails=$((fails + 1)); }
check() { local msg="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$msg"; else fail "$msg"; fi; }
py() { python3 "$ROOT/scripts/$@"; }
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT

echo "L0 skills"
for md in "$ROOT"/skills/*/SKILL.md; do
  dir="$(basename "$(dirname "$md")")"
  fm="$(awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} NR>1 {print}' "$md")"
  name="$(printf '%s\n' "$fm" | sed -n 's/^name:[[:space:]]*//p' | tr -d '"'"'")"
  desc="$(printf '%s\n' "$fm" | sed -n 's/^description:[[:space:]]*//p' | tr -d '"'"'")"
  [ "$name" = "$dir" ] && pass "$dir: name == folder" || fail "$dir: name '$name' != folder"
  [ -n "$desc" ] && [ "${#desc}" -le 1024 ] && pass "$dir: description present" || fail "$dir: description missing or over 1024 chars"
  if printf '%s\n' "$fm" | grep -q '^disable-model-invocation'; then fail "$dir: disable-model-invocation set"; fi
done
check "skills/ is flat" test -z "$(find "$ROOT/skills" -mindepth 3 -name SKILL.md)"

echo "L0 structure"
missing="$(cd "$ROOT" && find . -type d \( -name .git -o -name .claude-plugin -o -name __pycache__ -o -path './skills/*' -o -path './evals/fixtures/*/*' -o -path './evals/results/*' \) -prune -o -type d -print \
  | while read -r d; do [ -f "$d/README.md" ] || echo "$d"; done)"
[ -z "$missing" ] && pass "every folder has a README.md" || fail "folders without README.md: $(echo $missing)"
check "instructions/global.md is at most 250 words" test "$(wc -w < "$ROOT/instructions/global.md")" -le 250
for r in "$ROOT" "$FIX" "${EXTRA[@]}"; do
  label="$( [ "$r" = "$ROOT" ] && echo vanilla || { [ "$r" = "$FIX" ] && echo fixture || echo "$r"; })"
  if out="$(python3 -c "
import sys; sys.path.insert(0, '$ROOT/scripts'); import harness
p = harness.validate('$r') + harness.check_layout('$r', '$ROOT/LAYOUT.md')
print('\n'.join(p)); sys.exit(1 if p else 0)")"; then
    pass "$label: LAYOUT placement, paths, roles, graph shape"
  else
    fail "$label:"; printf '%s\n' "$out" | sed 's/^/         /'
  fi
  check "$label: README diagrams up to date" py graph.py "$r" --check-readme
done
check "root README diagram up to date" py graph.py "$ROOT" --check-readme

echo "L0 validator catches broken content"
broken() { # name, python mutation of wf (a dict); expects validation to fail
  local b="$T/broken-$1"; rm -rf "$b"; cp -r "$FIX" "$b"
  python3 -c "
import yaml; b='$b'; p=b+'/workflows/coding.yaml'; wf=yaml.safe_load(open(p)); n=wf['nodes']
$2
yaml.safe_dump(wf, open(p,'w'), sort_keys=False)"
  check "rejects: $1" bash -c "! python3 -c \"import sys; sys.path.insert(0, '$ROOT/scripts'); import harness; sys.exit(1 if harness.validate('$b') else 0)\""
}
broken "loop without a limit" "wf['defaults'].pop('max'); n['verify']['next'][0].pop('max')"
broken "missing step file" "n['verify']['step']='steps/nope.md'"
broken "role without a brief" "n['implement']['role']='ghost'"
broken "unreachable node" "n['orphan']={'step':'steps/verify.md','next':[{'to':'ready'}]}"
broken "dead end" "n['handover']['next']=[{'to':'handover'}]"
broken "workflow not routed" "w2=dict(wf); w2['name']='other'; yaml.safe_dump(w2, open(b+'/workflows/other.yaml','w'), sort_keys=False)"
b="$T/broken-layout"; rm -rf "$b"; cp -r "$FIX" "$b"; echo x > "$b/steps/notes.txt"
check "rejects: file outside LAYOUT" bash -c "! python3 -c \"import sys; sys.path.insert(0, '$ROOT/scripts'); import harness; sys.exit(1 if harness.check_layout('$b', '$ROOT/LAYOUT.md') else 0)\""

echo "L0 role boundaries (check-diff.sh)"
D="$ROOT/skills/work/check-diff.sh"; R="$FIX/roles"
g="$T/gitrepo"; mkdir -p "$g/src" "$g/tests"; echo a > "$g/src/app.py"
(cd "$g" && git init -q && git add . && git -c user.email=c@c -c user.name=c commit -qm init) || fail "git init"
b="$(git -C "$g" rev-parse HEAD)"
echo t > "$g/tests/test_app.py"
check "tests role may add tests" bash -c "cd '$g' && '$D' '$R/qa.md' $b"
check "nothing role may not touch tests" bash -c "cd '$g' && ! '$D' '$R/reviewer.md' $b"
echo x >> "$g/src/app.py"
check "tests role may not touch product code" bash -c "cd '$g' && ! '$D' '$R/qa.md' $b"
check "TESTS_ALLOW extends the tests role" bash -c "cd '$g' && TESTS_ALLOW='^src/app\.py$' '$D' '$R/qa.md' $b"
check "anything role may touch code" bash -c "cd '$g' && '$D' '$R/engineer.md' $b"
check "trace line written" bash -c "cd '$g' && HARNESS_TRACE='$T/trace' '$D' '$R/qa.md' $b; grep -q 'role=qa may_change=tests result=violation' '$T/trace'"

echo "L2 simulate"
for r in "$ROOT" "$FIX" "${EXTRA[@]}"; do
  if out="$(py simulate.py "$r")"; then pass "$(echo "$out" | tail -1) ($(basename "$r"))"; else fail "simulate $(basename "$r")"; echo "$out" | grep FAIL; fi
done

[ "$QUICK" = 1 ] && { echo; [ "$fails" = 0 ] && { echo "check: all passed (quick)"; exit 0; } || { echo "check: $fails failed"; exit 1; }; }

# ---------- L1 installer ----------
I="$ROOT/install.sh"
SKILLS="work customize-harness capture-knowledge"
snap() { (cd "$1" && find . \( -type f -o -type l \) -print0 | sort -z | xargs -0 -I{} sh -c 'printf "%s " "{}"; if [ -L "{}" ]; then readlink "{}"; else md5sum < "{}"; fi') ; }
run() { env -u XDG_CONFIG_HOME HOME="$1" bash "$I" "${@:2}"; }

echo "L1 install: all four tools"
h="$T/all"
mkdir -p "$h/.claude/skills" "$h/.config/opencode" "$h/.pi/agent" "$h/.omp/agent" "$h/.agents/skills/foreign"
printf 'keep me' > "$h/.claude/CLAUDE.md"
printf '# owner rules\n' > "$h/.config/opencode/AGENTS.md"
echo foreign > "$h/.agents/skills/foreign/SKILL.md"
# stale v1 links: task-loop and sanitize-pr no longer exist
ln -s "$h/.harness/skills/task-loop" "$h/.claude/skills/task-loop"
ln -s "$h/.harness/skills/sanitize-pr" "$h/.agents/skills/sanitize-pr"
before="$(snap "$h")"
run "$h" --dry-run > "$T/dry.out"
check "dry-run changes nothing" test "$before" = "$(snap "$h")"
check "dry-run reports actions" grep -q '^would: link' "$T/dry.out"
run "$h" > "$T/inst.out" || fail "install exited non-zero"
check "~/.harness links to repo" test "$(readlink "$h/.harness")" = "$ROOT"
for n in $SKILLS; do
  check "claude skill $n" test -f "$h/.claude/skills/$n/SKILL.md"
  check "agents skill $n" test -f "$h/.agents/skills/$n/SKILL.md"
done
check "stale v1 link task-loop removed" test ! -L "$h/.claude/skills/task-loop"
check "stale v1 link sanitize-pr removed" test ! -L "$h/.agents/skills/sanitize-pr"
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

echo "L1 re-run is idempotent"
after="$(snap "$h")"
run "$h" > /dev/null
check "second install changes nothing" test "$after" = "$(snap "$h")"

echo "L1 update: refresh block, drop stale links"
sed -i 's/^# psai harness$/# STALE/' "$h/.pi/agent/AGENTS.md"
ln -s "$h/.harness/skills/old-skill" "$h/.agents/skills/old-skill"
run "$h" > /dev/null
check "stale block refreshed" grep -q '^# psai harness$' "$h/.pi/agent/AGENTS.md"
check "stale skill link removed" test ! -L "$h/.agents/skills/old-skill"
check "state equals fresh install" test "$after" = "$(snap "$h")"

echo "L1 uninstall"
run "$h" --uninstall --dry-run > /dev/null
check "uninstall dry-run changes nothing" test "$after" = "$(snap "$h")"
run "$h" --uninstall > /dev/null || fail "uninstall exited non-zero"
check "~/.harness removed" test ! -e "$h/.harness"
check "no harness links left" test -z "$(find "$h/.claude/skills" "$h/.agents/skills" -maxdepth 1 -type l)"
check "CLAUDE.md content restored" grep -qx 'keep me' "$h/.claude/CLAUDE.md"
check "opencode AGENTS.md restored" cmp -s "$h/.config/opencode/AGENTS.md" "$h/.config/opencode/AGENTS.md.harness-backup"
check "created pi file removed" test ! -e "$h/.pi/agent/AGENTS.md"
check "created omp file removed" test ! -e "$h/.omp/agent/AGENTS.md"
check "foreign skill survives" test -f "$h/.agents/skills/foreign/SKILL.md"

echo "L1 only tools present"
h="$T/pionly"; mkdir -p "$h/.pi/agent"; run "$h" > /dev/null
check "no ~/.claude created" test ! -e "$h/.claude"
check "no opencode created" test ! -e "$h/.config/opencode"
check "no omp created" test ! -e "$h/.omp"
check "pi gets skills" test -f "$h/.agents/skills/work/SKILL.md"
h="$T/claudeonly"; mkdir -p "$h/.claude"; run "$h" > /dev/null
check "claude-only: no ~/.agents" test ! -e "$h/.agents"
check "claude-only: CLAUDE.md created" grep -Fxq "$imp" "$h/.claude/CLAUDE.md"

echo "L1 never clobber"
h="$T/clash"; mkdir -p "$h/.claude/skills/work" "$h/.pi/agent"
echo mine > "$h/.claude/skills/work/SKILL.md"
printf 'pi rules\n' > "$h/.pi/agent/CLAUDE.md"
run "$h" > /dev/null 2> "$T/clash.err"
check "existing skill dir kept" grep -qx mine "$h/.claude/skills/work/SKILL.md"
check "clash reported" grep -q 'not ours' "$T/clash.err"
check "pi uses its existing CLAUDE.md" grep -q harness:start "$h/.pi/agent/CLAUDE.md"
check "pi AGENTS.md not created" test ! -e "$h/.pi/agent/AGENTS.md"
h="$T/taken"; mkdir -p "$h/.harness" "$h/.claude"
check "refuses a foreign ~/.harness" test "$(run "$h" >/dev/null 2>&1; echo $?)" = 1

if [ "$DISCOVER" = 1 ]; then
  echo "L1 discovery (real tool binaries, temp HOME, no network calls)"
  h="$T/disc"; mkdir -p "$h/.claude" "$h/.config/opencode" "$h/.pi/agent" "$h/.omp/agent" "$h/w"
  run "$h" > /dev/null
  cd "$h/w" || exit 1
  if command -v opencode >/dev/null; then
    out="$(HOME="$h" XDG_CONFIG_HOME="$h/.config" XDG_DATA_HOME="$h/.d" XDG_CACHE_HOME="$h/.c" XDG_STATE_HOME="$h/.s" \
      timeout 120 opencode debug skill --pure 2>/dev/null)"
    for n in $SKILLS; do check "opencode sees $n once" test "$(printf '%s' "$out" | grep -c "\"name\": \"$n\"")" = 1; done
  fi
  if command -v pi >/dev/null; then
    out="$(echo '{"type":"get_commands"}' | HOME="$h" timeout 60 pi --mode rpc --no-session --offline 2>/dev/null)"
    for n in $SKILLS; do check "pi sees $n" grep -q "skill:$n\"" <<< "$out"; done
  fi
  if command -v omp >/dev/null; then
    out="$( (echo '{"type":"get_state"}'; sleep 10) | HOME="$h" ANTHROPIC_API_KEY=dummy timeout 90 omp --mode rpc --no-session --no-title 2>/dev/null)"
    for n in $SKILLS; do check "omp sees $n" grep -q "skill:$n\"" <<< "$out"; done
    check "omp loads global.md via import" grep -q 'Owner rules' <<< "$out"
  fi
  cd "$ROOT" || exit 1
fi

echo
if [ "$fails" = 0 ]; then echo "check: all passed"; else echo "check: $fails failed"; exit 1; fi
