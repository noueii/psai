#!/usr/bin/env bash
# Validate the harness (L0), its installer against temp HOMEs (L1) and its workflows by simulation (L2).
# Never touches the real HOME.
# Usage: scripts/check.sh [--quick] [--discover] [--upstream] [<extra-root>...]
#   --quick     skip the installer tests (what customize-harness runs while editing)
#   --discover  also ask the installed tools (opencode, pi, omp) which skills they see
#   --upstream  also fail if the tree ships any user-owned file (run this in psai itself, not in a fork)
#   <extra-root> also validate another harness root (L0 content checks + L2)
set -uo pipefail
unset HARNESS_TRACE   # our own check-diff tests must not write into an eval run's trace

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
FIX="$ROOT/evals/fixtures/harness-content"
[ -d "$FIX" ] || FIX=""   # L4 eval copies strip the test content; its self-tests are then skipped
QUICK=0; DISCOVER=0; UPSTREAM=0; EXTRA=()
for a in "$@"; do
  case "$a" in --quick) QUICK=1 ;; --discover) DISCOVER=1 ;; --upstream) UPSTREAM=1 ;; *) EXTRA+=("$a") ;; esac
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
for r in "$ROOT" ${FIX:+"$FIX"} ${EXTRA[@]+"${EXTRA[@]}"}; do
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
if [ "$UPSTREAM" = 1 ]; then
  shipped="$(cd "$ROOT" && git ls-files -co --exclude-standard | python3 -c "
import sys; sys.path.insert(0, 'scripts'); import harness
print('\n'.join(harness.user_files('.', 'LAYOUT.md', [l.strip() for l in sys.stdin if l.strip()])))")"
  [ -z "$shipped" ] && pass "upstream ships no user-owned file" || fail "upstream ships user-owned files: $(echo $shipped)"
fi

if [ -n "$FIX" ]; then
echo "L0 validator catches broken content"
broken() { # name, python mutation of wf (a dict); expects validation to fail
  local b="$T/broken-$1"; rm -rf "$b"; cp -r "$FIX" "$b"
  python3 -c "
import yaml; b='$b'; p=b+'/workflows/example.yaml'; wf=yaml.safe_load(open(p)); n=wf['nodes']
$2
yaml.safe_dump(wf, open(p,'w'), sort_keys=False)"
  check "rejects: $1" bash -c "! python3 -c \"import sys; sys.path.insert(0, '$ROOT/scripts'); import harness; sys.exit(1 if harness.validate('$b') else 0)\""
}
broken "loop without a limit" "wf['defaults'].pop('max')"
broken "missing step file" "n['check']['step']='steps/nope.md'"
broken "role without a brief" "n['do']['role']='ghost'"
broken "unreachable node" "n['orphan']={'step':'steps/do.md','next':[{'to':'ready'}]}"
broken "dead end" "n['report']['next']=[{'to':'report'}]"
broken "workflow not routed" "w2=dict(wf); w2['name']='other'; yaml.safe_dump(w2, open(b+'/workflows/other.yaml','w'), sort_keys=False)"
b="$T/broken-layout"; rm -rf "$b"; cp -r "$FIX" "$b"; echo x > "$b/steps/notes.txt"
check "rejects: file outside LAYOUT" bash -c "! python3 -c \"import sys; sys.path.insert(0, '$ROOT/scripts'); import harness; sys.exit(1 if harness.check_layout('$b', '$ROOT/LAYOUT.md') else 0)\""

echo "L0 role boundaries (check-diff.sh)"
D="$ROOT/skills/work/check-diff.sh"; R="$T/roles"; mkdir -p "$R"
for m in maker:anything tester:tests viewer:nothing; do printf -- '---\nmay_change: %s\n---\n' "${m#*:}" > "$R/${m%%:*}.md"; done
g="$T/gitrepo"; mkdir -p "$g/src" "$g/tests"; echo a > "$g/src/app.py"
(cd "$g" && git init -q && git add . && git -c user.email=c@c -c user.name=c commit -qm init) || fail "git init"
b="$(git -C "$g" rev-parse HEAD)"
echo t > "$g/tests/test_app.py"
check "tests role may add tests" bash -c "cd '$g' && '$D' '$R/tester.md' $b"
check "nothing role may not touch tests" bash -c "cd '$g' && ! '$D' '$R/viewer.md' $b"
echo x >> "$g/src/app.py"
check "tests role may not touch product code" bash -c "cd '$g' && ! '$D' '$R/tester.md' $b"
check "TESTS_ALLOW extends the tests role" bash -c "cd '$g' && TESTS_ALLOW='^src/app\.py$' '$D' '$R/tester.md' $b"
check "anything role may touch code" bash -c "cd '$g' && '$D' '$R/maker.md' $b"
check "trace line written" bash -c "cd '$g' && HARNESS_TRACE='$T/trace' '$D' '$R/tester.md' $b; grep -q 'role=tester may_change=tests result=violation' '$T/trace'"

echo "L0 engine trace (trace.sh)"
TR="$ROOT/skills/work/trace.sh"; tg="$T/tracerepo"; mkdir -p "$tg"; (cd "$tg" && git init -q)
trun() { (cd "$tg" && HARNESS_HOME="$FIX" "$TR" example "$1") >/dev/null 2>&1; }
check "refuses a run that doesn't begin at start" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; ! trun ready"
check "records start" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; trun do"
check "refuses leaving a role node before check-diff" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; ! trun check"
echo "check-diff role=doer may_change=anything result=ok files=1" >> "$tg/.git/harness-trace"
check "refuses a move that isn't an edge" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; ! trun report"
check "allows the edge after check-diff" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; trun check"
echo "check-diff role=checker may_change=nothing result=ok files=0" >> "$tg/.git/harness-trace"
check "escalate resumes the asker" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; trun escalate && trun check"

fi

echo "L2 simulate"
for r in "$ROOT" ${FIX:+"$FIX"} ${EXTRA[@]+"${EXTRA[@]}"}; do
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

echo "L1 owner rules (instructions/owner.md)"
fk="$T/ownerfork"; cp -r "$ROOT" "$fk"; rm -rf "$fk/.git"; echo "- Ask before deleting anything." > "$fk/instructions/owner.md"
h="$T/owner"; mkdir -p "$h/.claude" "$h/.pi/agent"
env -u XDG_CONFIG_HOME HOME="$h" bash "$fk/install.sh" > /dev/null
check "claude imports global.md and owner.md" bash -c "grep -Fxq '$imp' '$h/.claude/CLAUDE.md' && grep -Fxq '@~/.harness/instructions/owner.md' '$h/.claude/CLAUDE.md'"
check "pi block inlines owner.md" grep -q 'Ask before deleting anything' "$h/.pi/agent/AGENTS.md"
a1="$(snap "$h")"; env -u XDG_CONFIG_HOME HOME="$h" bash "$fk/install.sh" > /dev/null
check "owner.md install is idempotent" test "$a1" = "$(snap "$h")"
env -u XDG_CONFIG_HOME HOME="$h" bash "$fk/install.sh" --uninstall > /dev/null
check "uninstall removes both imports" test ! -e "$h/.claude/CLAUDE.md"

echo "L1 a fork takes upstream updates without conflicts"
G="git -c user.email=t@t -c user.name=t"
up="$T/upstream"; mkdir -p "$up"
(cd "$ROOT" && git ls-files -co --exclude-standard -z | xargs -0 cp --parents -t "$up" 2>/dev/null)
(cd "$up" && git init -q -b main && git add -A && $G commit -qm upstream) || fail "upstream repo"
git clone -q "$up" "$T/fork"; f="$T/fork"
if [ -n "$FIX" ]; then cp -r "$FIX"/workflows "$FIX"/steps "$FIX"/roles "$FIX"/guides "$FIX"/templates "$FIX"/knowledge "$f/"; rm -f "$f"/*/README.md.fix; fi
# the fixture's folders have no READMEs of their own, so the fork keeps upstream's
echo "- Ask before deleting anything." > "$f/instructions/owner.md"
printf '# Inbox\n\n## 2026-01-01: a finding\n- Tag: fact\n' > "$f/knowledge/inbox.md"
python3 "$f/scripts/graph.py" "$f" --update-readme > /dev/null
(cd "$f" && git add -A && $G commit -qm "my stack") || fail "fork commit"
user_before="$(cd "$f" && git ls-files | python3 -c "
import sys; sys.path.insert(0, 'scripts'); import harness
print('\n'.join(harness.user_files('.', 'LAYOUT.md', [l.strip() for l in sys.stdin])))" | xargs md5sum)"
(cd "$up" && for x in README.md LAYOUT.md instructions/global.md skills/*/SKILL.md docs/decisions/*.md $(git ls-files '*README.md'); do echo "<!-- upstream change -->" >> "$x"; done \
  && echo "# upstream change" >> install.sh && echo "# upstream change" >> scripts/check.sh && $G commit -qam "upstream update")
(cd "$f" && git remote add upstream "$up" && $G pull -q --no-rebase --no-edit upstream main) > "$T/merge.out" 2>&1
check "git pull upstream main merges cleanly" bash -c "! grep -qi conflict '$T/merge.out' && test -z \"\$(git -C '$f' diff --name-only --diff-filter=U)\""
check "upstream changes arrived" grep -q 'upstream change' "$f/LAYOUT.md"
check "user files untouched by the merge" bash -c "cd '$f' && echo '$user_before' | md5sum -c --quiet"
check "the fork still validates" python3 -c "
import sys; sys.path.insert(0, '$f/scripts'); import harness
sys.exit(1 if harness.validate('$f') + harness.check_layout('$f', '$f/LAYOUT.md') else 0)"

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
    check "omp loads global.md via import" grep -q 'psai harness' <<< "$out"
  fi
  cd "$ROOT" || exit 1
fi

echo
if [ "$fails" = 0 ]; then echo "check: all passed"; else echo "check: $fails failed"; exit 1; fi
