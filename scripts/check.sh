#!/usr/bin/env bash
# Validate the harness (L0), its installer against temp HOMEs (L1) and its workflows by simulation (L2).
# Never touches the real HOME.
# Usage: scripts/check.sh [--quick] [--discover] [--upstream] [<extra-root>...]
#   --quick     skip the installer tests (what customize-harness runs while editing)
#   --discover  also ask the installed tools (opencode, pi, omp) which skills they see
#   --upstream  also fail if the tree ships any user-owned file (run this in psai itself, not in a fork)
#   <extra-root> also validate another harness root (L0 content checks + L2)
set -uo pipefail
unset PSAI_TRACE PSAI_STATE PSAI_EVAL   # our own tests must not write into an eval run's trace or this machine's state

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
export PSAI_STATE="$T/state"   # any state a test writes stays in the temp dir (tests that need their own set it)

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
missing="$(cd "$ROOT" && find . -type d \( -name .git -o -name .claude-plugin -o -name __pycache__ -o -name .skills-cache -o -name .state -o -path './skills/*' -o -path './my-skills/*' -o -path './evals/fixtures/*/*' -o -path './evals/results/*' \) -prune -o -type d -print \
  | while read -r d; do [ -f "$d/README.md" ] || echo "$d"; done)"
[ -z "$missing" ] && pass "every folder has a README.md" || fail "folders without README.md: $(echo $missing)"
check "instructions/global.md is at most 120 words" test "$(wc -w < "$ROOT/instructions/global.md")" -le 120
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
if [ -n "$FIX" ]; then  # the sync-tail overlay: the example workflow ending report -> retro -> sync -> ready (skill nodes)
  st="$T/synctail"; mkdir -p "$st"; (cd "$ROOT" && git ls-files -co --exclude-standard -z | xargs -0 cp --parents -t "$st" 2>/dev/null)
  cp -r "$FIX"/. "$st/"; cp -r "$ROOT/evals/fixtures/sync-tail/workflows" "$ROOT/evals/fixtures/sync-tail/steps" "$st/"
  check "fixture + sync-tail: skill nodes without a step validate" python3 -c "import sys; sys.path.insert(0, '$ROOT/scripts'); import harness; sys.exit(1 if harness.validate('$st') + harness.check_layout('$st', '$ROOT/LAYOUT.md') else 0)"
  check "fixture + sync-tail: simulates and its diagram is fresh" bash -c "python3 '$ROOT/scripts/simulate.py' '$st' >/dev/null && python3 '$ROOT/scripts/graph.py' '$st' --check-readme"
fi
# The base folder is ~/.psai (and <repo>/.psai/). Exempt: decision records (history), this file (it builds the old
# layout to test the upgrade, as does test-sync.sh), migrations/ (upgrade code) and lines marked "legacy".
old_paths="$(cd "$ROOT" && { git ls-files -co --exclude-standard 2>/dev/null || find . -type f ! -path './.git/*' | sed 's|^\./||'; } \
  | grep -v -e '^docs/decisions/' -e '^migrations/' -e '^scripts/check\.sh$' -e '^scripts/test-sync\.sh$' -e '^evals/results/' | while IFS= read -r x; do [ -f "$x" ] && printf '%s\0' "$x"; done \
  | xargs -0 grep -nIE '(^|[^[:alnum:]_])\.harness([^[:alnum:]_-]|$)' 2>/dev/null | grep -v legacy)"
[ -z "$old_paths" ] && pass "no ~/.harness path left (the base folder is ~/.psai)" || { fail "old ~/.harness paths:"; printf '%s\n' "$old_paths" | sed 's/^/         /'; }
# Skills, plugins and steps find files by name (psai resolve/route/node), never by a path into the home. Exempt: the
# plugins' bootstrap lines (marked psai-bootstrap). ADR 0011, section 5.
hard="$(cd "$ROOT" && git ls-files -co --exclude-standard -- skills plugins 'evals/fixtures/*/steps/*.md' 'evals/fixtures/stacks/*/steps/*.md' 2>/dev/null \
  | while IFS= read -r x; do [ -f "$x" ] && printf '%s\0' "$x"; done | xargs -0 grep -nIE '(~/\.psai/|\$\{?PSAI_HOME\}?/|\$HOME/\.psai|"\.psai")' 2>/dev/null | grep -v psai-bootstrap)"
[ -z "$hard" ] && pass "no hard-coded ~/.psai or \$PSAI_HOME path in skills, plugins or steps" || { fail "hard-coded home paths:"; printf '%s\n' "$hard" | sed 's/^/         /'; }
# There is no repo-level .psai/ layer (ADR 0011, Q2). Exempt: decision records and this file.
repo_layer="$(cd "$ROOT" && git ls-files -co --exclude-standard 2>/dev/null | grep -v -e '^docs/decisions/' -e '^scripts/check\.sh$' -e '^evals/results/' \
  | while IFS= read -r x; do [ -f "$x" ] && printf '%s\0' "$x"; done | xargs -0 grep -nIE "(<repo>/\.psai|\.psai/workflows|repo's \.psai|\"\.psai\", \"workflows)" 2>/dev/null)"
[ -z "$repo_layer" ] && pass "no repo-level .psai/ layer left" || { fail "repo-level .psai/ references:"; printf '%s\n' "$repo_layer" | sed 's/^/         /'; }

echo "L0 skills (harness.py skills check: roles' skills resolve; reads your tool folders, never writes)"
E="$T/emptyhome"; mkdir -p "$E"
for r in "$ROOT" ${FIX:+"$FIX"} ${EXTRA[@]+"${EXTRA[@]}"}; do
  label="$( [ "$r" = "$ROOT" ] && echo vanilla || { [ "$r" = "$FIX" ] && echo fixture || echo "$r"; })"
  # the fixture is test content: resolve it against an empty HOME so the result doesn't depend on this machine
  if [ "$r" = "$FIX" ]; then out="$(cd "$T" && HOME="$E" python3 "$ROOT/scripts/harness.py" skills check --root "$r")"; rc=$?
  else out="$(python3 "$ROOT/scripts/harness.py" skills check --root "$r")"; rc=$?; fi
  [ "$rc" = 0 ] && pass "$label: required skills resolve, skills.yaml and my-skills/ valid" || fail "$label: skills"
  printf '%s\n' "$out" | grep -v '^  ok' | sed 's/^  /  /'
done

echo "L0 injected nudge (harness.py context)"
gen="$T/gen"; mkdir -p "$gen"; cp -r "$ROOT/instructions" "$ROOT/skills" "$gen/"; mkdir -p "$gen/workflows"
[ -n "$FIX" ] && cp -r "$FIX"/workflows "$FIX"/steps "$FIX"/roles "$FIX"/guides "$FIX"/templates "$FIX"/knowledge "$gen/"
check "generator is deterministic" bash -c "[ \"\$(python3 '$ROOT/scripts/harness.py' context '$gen' '~/.psai')\" = \"\$(python3 '$ROOT/scripts/harness.py' context '$gen' '~/.psai')\" ]"
for w in "$gen"/workflows/*.yaml; do
  case "$w" in *.cases.yaml|*/ROUTING.yaml|*'*'*) continue ;; esac
  n="$(basename "$w" .yaml)"; check "nudge lists workflow $n" bash -c "python3 '$ROOT/scripts/harness.py' context '$gen' | grep -q '^- $n: '"
done
check "nudge says how to add or change a skill" bash -c "python3 '$ROOT/scripts/harness.py' context '$ROOT' | grep -q 'To add or change a skill, use customize-harness'"
check "nudge names the router skill" bash -c "python3 '$ROOT/scripts/harness.py' context '$ROOT' | grep -q 'request-router'"
check "PSAI_ROLE gives the role-mode nudge, without routing" bash -c "o=\"\$(PSAI_ROLE=doer python3 '$ROOT/scripts/harness.py' context '$gen')\"; grep -q 'You are the doer inside a running psai workflow' <<< \"\$o\" && ! grep -q 'run the request-router skill first' <<< \"\$o\" && ! grep -q '^- example: ' <<< \"\$o\""
echo "  info nudge size: $(python3 "$ROOT/scripts/harness.py" context "$ROOT" '~/.psai' | wc -w) words vanilla, $(python3 "$ROOT/scripts/harness.py" context "$gen" '~/.psai' | wc -w) with the test workflow"
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

echo "L0 skill checks catch broken setups"
sk() { HOME="$E" python3 "$ROOT/scripts/harness.py" skills check --root "$1" --project "${2:-$T}" --json; }
skbad() { # name, shell mutation of a copy of the fixture in $b; expects check to fail
  b="$T/skbad-$(printf '%s' "$1" | tr -c 'a-z0-9' '-')"; rm -rf "$b"; cp -r "$FIX" "$b"; (cd "$b" && eval "$2")
  check "rejects: $1" bash -c "! python3 -c \"import sys; sys.path.insert(0, '$ROOT/scripts'); import harness; sys.exit(1 if harness.validate('$b') else 0)\" || ! HOME='$E' python3 '$ROOT/scripts/harness.py' skills check --root '$b' --project '$T' >/dev/null"
}
skbad "required skill that resolves nowhere" "rm -rf my-skills/change-notes"
skbad "unpinned skills.yaml entry" "printf 'skills:\n  - {name: pk, source: github:o/r, path: pk, ref: main}\n' > skills.yaml"
skbad "skills.yaml entry without a ref" "printf 'skills:\n  - {name: pk, source: github:o/r, path: pk}\n' > skills.yaml"
skbad "a role that lists work or request-router" "sed -i 's/required: \[change-notes\]/required: [change-notes, request-router]/' roles/doer.md"
skbad "my-skills name != folder" "sed -i 's/^name: change-notes/name: other/' my-skills/change-notes/SKILL.md"
skbad "a loose file in my-skills/" "echo x > my-skills/notes.md"
skbad "my-skills clashing with psai's skills/" "mkdir -p skills/change-notes && cp my-skills/change-notes/SKILL.md skills/change-notes/"
b="$T/skproj"; rm -rf "$b"; cp -r "$FIX" "$b"; p="$T/proj"; mkdir -p "$p/.agents/skills"; mv "$b/my-skills/change-notes" "$p/.agents/skills/"
check "warns: a required skill that is project-only (make it optional)" bash -c "$(declare -f sk); E='$E' ROOT='$ROOT' T='$T'; sk '$b' '$p' | grep -q 'make it optional'"
mkdir -p "$E/.agents/skills/change-notes"; cp "$FIX/my-skills/change-notes/SKILL.md" "$E/.agents/skills/change-notes/"
check "warns: a duplicate skill name (prefix your own)" bash -c "$(declare -f sk); E='$E' ROOT='$ROOT' T='$T'; sk '$FIX' | grep -q 'prefix your own skills'"
check "a real copy in a tool folder counts as unmanaged" bash -c "$(declare -f sk); E='$E' ROOT='$ROOT' T='$T'; sk '$FIX' | python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin)[\"unmanaged\"] == [\"change-notes\"] else 1)'"
rm -rf "$E/.agents"
check "brief lists the role's skills with use-when and path" bash -c "PSAI_HOME='$FIX' HOME='$E' python3 '$ROOT/scripts/harness.py' skills brief '$FIX/roles/doer.md' '$FIX/steps/do.md' | grep -q '^Your skills: change-notes (use when you change files in a repo; $FIX/my-skills/change-notes/SKILL.md)'"
check "brief: missing required skill exits 3 and says escalate" bash -c "cd '$T'; out=\"\$(PSAI_HOME='$T/skbad-required-skill-that-resolves-nowhere' HOME='$E' python3 '$ROOT/scripts/harness.py' skills brief '$FIX/roles/doer.md')\"; test \$? = 3 && grep -q 'escalate first' <<< \"\$out\""
b="$T/skopt"; rm -rf "$b"; cp -r "$FIX" "$b"; sed -i 's/required: \[change-notes\]/required: []\n  optional: [nope]/' "$b/roles/doer.md"
check "brief: missing optional skill is noted, exit 0" bash -c "cd '$T'; PSAI_HOME='$b' HOME='$E' python3 '$ROOT/scripts/harness.py' skills brief '$b/roles/doer.md' | grep -q 'Missing optional skills: nope. Note them in the final report'"

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
check "trace line written" bash -c "cd '$g' && PSAI_TRACE='$T/trace' '$D' '$R/tester.md' $b; grep -q 'role=tester may_change=tests result=violation' '$T/trace'"

echo "L0 engine trace (trace.sh)"
TR="$ROOT/skills/work/trace.sh"; tg="$T/tracerepo"; mkdir -p "$tg"; (cd "$tg" && git init -q)
trun() { (cd "$tg" && PSAI_HOME="$FIX" "$TR" example "$1") >/dev/null 2>&1; }
check "refuses a run that doesn't begin at start" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; ! trun ready"
check "records start" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; trun do"
check "refuses leaving a role node before check-diff" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; ! trun check"
echo "check-diff role=doer may_change=anything result=ok files=1" >> "$tg/.git/psai-trace"
check "refuses a move that isn't an edge" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; ! trun report"
check "allows the edge after check-diff" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; trun check"
echo "check-diff role=checker may_change=nothing result=ok files=0" >> "$tg/.git/psai-trace"
check "escalate resumes the asker" bash -c "$(declare -f trun); TR='$TR' tg='$tg' FIX='$FIX'; trun escalate && trun check"
check "psai trace runs trace.sh (refuses a non-edge)" bash -c "cd '$tg' && ! PSAI_HOME='$FIX' python3 '$ROOT/scripts/psai.py' trace example ready"

echo "L0 engine lookups (psai route, node, check-diff; single root)"
P() { (cd "$tg" && PSAI_HOME="$FIX" HOME="$E" python3 "$ROOT/scripts/psai.py" "$@") 2>/dev/null; }
check "psai route prints the tree and each workflow's when" bash -c "$(declare -f P); tg='$tg' FIX='$FIX' E='$E' ROOT='$ROOT'; o=\"\$(P route)\"; grep -q 'workflow: example' <<< \"\$o\" && grep -q '^- example: Any task' <<< \"\$o\" && grep -q 'Escalation block: .*/skills/work/escalation.md' <<< \"\$o\""
check "psai node: step, reads, brief, knowledge, skills, edges" bash -c "$(declare -f P); tg='$tg' FIX='$FIX' E='$E' ROOT='$ROOT'; o=\"\$(P node example do)\"; grep -q '^step: $FIX/steps/do.md' <<< \"\$o\" && grep -q '^  brief: $FIX/roles/doer.md' <<< \"\$o\" && grep -q '^  knowledge: $FIX/knowledge/roles/doer/INDEX.md' <<< \"\$o\" && grep -q 'Your skills: change-notes' <<< \"\$o\" && grep -q '^next: blocked -> escalate' <<< \"\$o\""
check "psai node: a missing required skill exits 3" bash -c "cd '$tg' && PSAI_HOME='$T/skbad-required-skill-that-resolves-nowhere' HOME='$E' python3 '$ROOT/scripts/psai.py' node example do >/dev/null 2>&1; test \$? = 3"
check "psai check-diff <workflow> <node> <base> uses the node's brief" bash -c "cd '$g' && PSAI_HOME='$FIX' python3 '$ROOT/scripts/psai.py' check-diff example check $b 2>/dev/null | grep -q 'BOUNDARY VIOLATION (checker, may_change: nothing)'"

echo "L0 psai resolve and stack.yaml (scripts/test-resolve.sh; fixture stacks in a temp PSAI_HOME)"
while IFS= read -r line; do
  case "$line" in "  ok   "*) pass "${line#  ok   }" ;; "  FAIL "*) fail "${line#  FAIL }" ;; esac
done < <("$ROOT/scripts/test-resolve.sh" 2>/dev/null)

fi

echo "L2 simulate"
for r in "$ROOT" ${FIX:+"$FIX"} ${EXTRA[@]+"${EXTRA[@]}"}; do
  if out="$(py simulate.py "$r")"; then pass "$(echo "$out" | tail -1) ($(basename "$r"))"; else fail "simulate $(basename "$r")"; echo "$out" | grep FAIL; fi
done

[ "$QUICK" = 1 ] && { echo; [ "$fails" = 0 ] && { echo "check: all passed (quick)"; exit 0; } || { echo "check: $fails failed"; exit 1; }; }

# ---------- L1 installer ----------
I="$ROOT/install.sh"
SKILLS="$(cd "$ROOT/skills" && ls -d */ | tr -d / | tr '\n' ' ')"
snap() { (cd "$1" && find . \( -path ./.claude/plugins -o -path ./.claude/backups -o -name .claude.json -o -name '.claude.json.*' \) -prune -o \( -type f -o -type l \) -print0 | sort -z | xargs -0 -I{} sh -c 'printf "%s " "{}"; if [ -L "{}" ]; then readlink "{}"; else md5sum < "{}"; fi') ; }
run() { env -u XDG_CONFIG_HOME -u PSAI_HOME PSAI_STATE="$1/.psai-state" HOME="$1" bash "$I" "${@:2}"; }   # state per temp HOME
has_cli() { command -v "$1" >/dev/null; }
enabled() { python3 -c "import json,sys; s=json.load(open('$1/.claude/settings.json')); sys.exit(0 if (s.get('enabledPlugins') or {}).get('psai@psai') else 1)" 2>/dev/null; }

echo "L1 install: all four tools, upgrading from v1 and the old ~/.harness base link"
h="$T/all"
mkdir -p "$h/.claude/skills" "$h/.config/opencode" "$h/.pi/agent" "$h/.omp/agent" "$h/.agents/skills/foreign"
printf 'keep me\n@~/.harness/instructions/global.md\n' > "$h/.claude/CLAUDE.md"          # a v1 import line
printf '# owner rules\n\n<!-- harness:start -->\nold\n<!-- harness:end -->\n' > "$h/.config/opencode/AGENTS.md"   # a v1 block
printf '<!-- harness:start -->\nold\n<!-- harness:end -->\n' > "$h/.pi/agent/AGENTS.md"
echo foreign > "$h/.agents/skills/foreign/SKILL.md"
ln -s "$h/.harness/skills/task-loop" "$h/.claude/skills/task-loop"      # stale v1 skill links
ln -s "$h/.harness/skills/sanitize-pr" "$h/.agents/skills/sanitize-pr"
ln -s "$ROOT" "$h/.harness"                                              # the pre-rename base link
ln -s "$h/.harness/skills/work" "$h/.claude/skills/work"                 # and links made through it
mkdir -p "$h/.pi/agent/extensions"; ln -s "$h/.harness/plugins/pi/psai.ts" "$h/.pi/agent/extensions/psai.ts"
before="$(snap "$h")"
run "$h" --dry-run > "$T/dry.out" 2>&1
check "dry-run changes nothing" test "$before" = "$(snap "$h")"
check "dry-run reports actions" grep -q '^would: link' "$T/dry.out"
check "dry-run reports the new home and the old link's removal" bash -c "grep -q '^would: link $h/.psai/framework -> ' '$T/dry.out' && grep -q '^would: create the overlay' '$T/dry.out' && grep -q '^would: unlink old base $h/.harness' '$T/dry.out'"
run "$h" > "$T/inst.out" 2>&1 || fail "install exited non-zero"
check "~/.psai is a home: framework/ links the repo; overlay, stacks, state" bash -c "test -d '$h/.psai' -a ! -L '$h/.psai' && test \"\$(readlink '$h/.psai/framework')\" = '$ROOT' && test -d '$h/.psai/stacks'"
check "the overlay is a git repo, the stack nostack, with an empty stacks.yaml" bash -c "git -C '$h/.psai/overlay' rev-parse HEAD && grep -q '^name: nostack' '$h/.psai/overlay/stack.yaml' && grep -q '^stacks: \[\]' '$h/.psai/overlay/stacks.yaml'"
check "old ~/.harness link (to a psai clone) removed" test ! -e "$h/.harness" -a ! -L "$h/.harness"
check "skill linked through the old path relinked" test "$(readlink "$h/.claude/skills/work")" = "$h/.psai/framework/skills/work"
for n in $SKILLS; do
  check "claude skill $n" test -f "$h/.claude/skills/$n/SKILL.md"
  check "agents skill $n" test -f "$h/.agents/skills/$n/SKILL.md"
done
check "stale v1 skill links removed" bash -c "test ! -L '$h/.claude/skills/task-loop' && test ! -L '$h/.agents/skills/sanitize-pr'"
check "foreign skill untouched" grep -qx foreign "$h/.agents/skills/foreign/SKILL.md"
check "v1 import line removed, content kept" bash -c "! grep -q '@~/.harness' '$h/.claude/CLAUDE.md' && grep -qx 'keep me' '$h/.claude/CLAUDE.md'"
check "v1 opencode block removed, content kept" bash -c "! grep -q harness:start '$h/.config/opencode/AGENTS.md' && grep -qx '# owner rules' '$h/.config/opencode/AGENTS.md'"
check "v1 pi file (only our block) removed" test ! -e "$h/.pi/agent/AGENTS.md"
check "pi extension linked" test "$(readlink "$h/.pi/agent/extensions/psai.ts")" = "$h/.psai/framework/plugins/pi/psai.ts"
check "omp extension linked" test "$(readlink "$h/.omp/agent/extensions/psai.ts")" = "$h/.psai/framework/plugins/omp/psai.ts"
check "opencode stub imports the live plugin" grep -Fq "$h/.psai/framework/plugins/opencode/psai.js" "$h/.config/opencode/plugin/psai.js"
check "the psai command linked into ~/.local/bin and runs" bash -c "test \"\$(readlink '$h/.local/bin/psai')\" = '$h/.psai/framework/scripts/psai.py' && HOME='$h' PSAI_STATE='$h/.psai-state' '$h/.local/bin/psai' status | grep -q '^install: matches HEAD'"
check "the nudge reaches a session from the home" bash -c "HOME='$h' PSAI_STATE='$h/.psai-state' bash '$ROOT/plugins/claude/hooks/session-start.sh' < /dev/null | grep -q 'python3 ~/.psai/framework/scripts/psai.py'"
check "migrations recorded once; installed commit recorded" bash -c "grep -q 0001-remove-old-harness-link '$h/.psai-state/migrations.json' && grep -q \"\$(git -C '$ROOT' rev-parse HEAD)\" '$h/.psai-state/installed.json'"
if has_cli claude; then
  check "claude plugin psai@psai enabled, marketplace at ~/.psai/framework" bash -c "$(declare -f enabled); enabled '$h' && grep -q '\"path\": \"$h/.psai/framework\"' '$h/.claude/settings.json'"
else echo "  skip claude plugin install (claude CLI not found)"; fi

echo "L1 re-run is idempotent"
after="$(snap "$h")"
run "$h" > /dev/null 2>&1
check "second install changes nothing" test "$after" = "$(snap "$h")"
ln -s "$h/.psai/framework/skills/old-skill" "$h/.agents/skills/old-skill"
run "$h" > /dev/null 2>&1
check "stale skill link removed on update" test ! -L "$h/.agents/skills/old-skill"

echo "L1 the nudge reaches each session (no AI, no network)"
while IFS= read -r line; do
  case "$line" in "  ok   "*) pass "${line#  ok   }" ;; "  FAIL "*) fail "${line#  FAIL }" ;; "  skip "*) echo "$line" ;; esac
done < <("$ROOT/scripts/test-plugins.sh" 2>/dev/null)

echo "L1 sync, retro, ledger and migrations (no AI, no network; scripts/test-sync.sh)"
while IFS= read -r line; do
  case "$line" in "  ok   "*) pass "${line#  ok   }" ;; "  FAIL "*) fail "${line#  FAIL }" ;; "  skip "*) echo "$line" ;; "L1 "*) echo "  -- ${line#L1 }" ;; esac
done < <("$ROOT/scripts/test-sync.sh" 2>/dev/null)

echo "L1 uninstall"
run "$h" --uninstall --dry-run > /dev/null 2>&1
check "uninstall dry-run changes nothing" test "$after" = "$(snap "$h")"
run "$h" --uninstall > /dev/null 2>&1 || fail "uninstall exited non-zero"
check "framework/ unlinked; the overlay and stacks are kept" bash -c "test ! -e '$h/.psai/framework' -a ! -L '$h/.psai/framework' && git -C '$h/.psai/overlay' rev-parse HEAD && test -d '$h/.psai/stacks'"
check "no harness links left" test -z "$(find "$h/.claude/skills" "$h/.agents/skills" "$h/.pi/agent/extensions" "$h/.omp/agent/extensions" -maxdepth 1 -type l)"
check "opencode stub removed" test ! -e "$h/.config/opencode/plugin/psai.js"
check "psai command unlinked" test ! -L "$h/.local/bin/psai"
has_cli claude && check "claude plugin removed" bash -c "$(declare -f enabled); ! enabled '$h'"
check "owner content survives" bash -c "grep -qx 'keep me' '$h/.claude/CLAUDE.md' && grep -qx '# owner rules' '$h/.config/opencode/AGENTS.md'"
check "foreign skill survives" test -f "$h/.agents/skills/foreign/SKILL.md"

echo "L1 only tools present"
h="$T/pionly"; mkdir -p "$h/.pi/agent"; run "$h" > /dev/null 2>&1
check "no ~/.claude, opencode or omp created" bash -c "test ! -e '$h/.claude' && test ! -e '$h/.config/opencode' && test ! -e '$h/.omp'"
check "pi gets skills and its extension" bash -c "test -f '$h/.agents/skills/work/SKILL.md' && test -L '$h/.pi/agent/extensions/psai.ts'"

echo "L1 migration 0002: a fork-layout ~/.psai (a link to a fork clone) becomes a home"
fk2="$T/fork2"; mkdir -p "$fk2"; (cd "$ROOT" && git ls-files -co --exclude-standard -z | xargs -0 cp --parents -t "$fk2" 2>/dev/null)
[ -n "$FIX" ] && cp -r "$FIX"/workflows "$FIX"/steps "$FIX"/roles "$FIX"/guides "$FIX"/templates "$FIX"/knowledge "$FIX"/my-skills "$fk2/"
echo "- Ask before deleting anything." > "$fk2/instructions/owner.md"
(cd "$fk2" && git init -q -b main && git add -A && git -c user.email=t@t -c user.name=t commit -qm fork) || fail "fork2 repo"
printf '# Inbox\n\n## 2026-11-22: a local entry\n- Tag: fact\n' > "$fk2/knowledge/inbox.md"; mkdir -p "$fk2/.state"; echo '{"last_sync": "x"}' > "$fk2/.state/sync.json"
h="$T/mig"; mkdir -p "$h/.agents/skills" "$h/.pi/agent"; ln -s "$fk2" "$h/.psai"; ln -s "$h/.psai/skills/work" "$h/.agents/skills/work"
mrun() { env -u XDG_CONFIG_HOME -u PSAI_HOME -u PSAI_STATE HOME="$h" bash "$fk2/install.sh" "$@"; }
tracked() { (cd "$fk2" && git ls-files -z | xargs -0 md5sum | md5sum); }
t0="$(tracked)"; before="$(snap "$h")"
mrun --dry-run > "$T/mig-dry.out" 2>&1
check "0002 dry-run changes nothing and says what it would do" bash -c "test '$before' = \"\$(cd '$h' && $(declare -f snap); snap '$h')\" && test -L '$h/.psai' && grep -q '^would: turn $h/.psai' '$T/mig-dry.out' && grep -q '^would: copy instructions/owner.md into the overlay' '$T/mig-dry.out'"
mrun > "$T/mig.out" 2>&1 || { fail "install from a fork-layout home"; cat "$T/mig.out"; }
check "~/.psai is now a home; framework/ links the fork clone" bash -c "test -d '$h/.psai' -a ! -L '$h/.psai' && test \"\$(readlink '$h/.psai/framework')\" = '$fk2'"
check "the fork's files are in the overlay, committed" bash -c "o='$h/.psai/overlay'; test -f \$o/workflows/example.yaml -a -f \$o/my-skills/change-notes/SKILL.md && grep -q 'Ask before deleting' \$o/instructions/owner.md && grep -q 'a local entry' \$o/knowledge/inbox.md && test -z \"\$(git -C \$o status --porcelain)\""
check ".state moved to state/" bash -c "grep -q last_sync '$h/.psai/state/sync.json' && test ! -e '$fk2/.state'"
check "the clone's tracked files are untouched" test "$t0" = "$(tracked)"
check "a skill link through the old layout is relinked" test "$(readlink "$h/.agents/skills/work")" = "$h/.psai/framework/skills/work"
check "0002 recorded as run; the overlay's workflow resolves and reaches the nudge" bash -c "grep -q 0002-fork-to-stacks '$h/.psai/state/migrations.json' && test \"\$(HOME='$h' python3 '$ROOT/scripts/psai.py' resolve workflow example)\" = '$h/.psai/overlay/workflows/example.yaml' && HOME='$h' bash '$ROOT/plugins/claude/hooks/session-start.sh' < /dev/null | grep -q -- '- nostack:example: '"
after="$(snap "$h")"; mrun > /dev/null 2>&1
check "re-run after the conversion changes nothing" test "$after" = "$(snap "$h")"
mrun --relink > "$T/relink.out" 2>&1
check "--relink only relinks skills (nothing to do here)" bash -c "test '$after' = \"\$(cd '$h' && $(declare -f snap); snap '$h')\" && ! grep -q 'claude\\|extensions\\|migration' '$T/relink.out'"

echo "L1 never clobber"
h="$T/clash"; mkdir -p "$h/.claude/skills/work" "$h/.pi/agent/extensions" "$h/.config/opencode/plugin"
echo mine > "$h/.claude/skills/work/SKILL.md"; echo mine > "$h/.pi/agent/extensions/psai.ts"; echo mine > "$h/.config/opencode/plugin/psai.js"
run "$h" > /dev/null 2> "$T/clash.err"
check "existing skill, extension and plugin kept" bash -c "grep -qx mine '$h/.claude/skills/work/SKILL.md' && grep -qx mine '$h/.pi/agent/extensions/psai.ts' && grep -qx mine '$h/.config/opencode/plugin/psai.js'"
check "clashes reported" test "$(grep -c 'not ours' "$T/clash.err")" -ge 3
h="$T/taken"; mkdir -p "$h/.claude"; echo x > "$h/.psai"
check "refuses a ~/.psai that is a file" test "$(run "$h" >/dev/null 2>&1; echo $?)" = 1
h="$T/taken2"; mkdir -p "$h/.claude" "$h/.psai" "$T/notpsai"; ln -s "$T/notpsai" "$h/.psai/framework"
check "refuses a framework/ that links something else" test "$(run "$h" >/dev/null 2>&1; echo $?)" = 1
h="$T/taken3"; mkdir -p "$h/.claude"; ln -s "$T/notpsai" "$h/.psai"
check "refuses a ~/.psai link to something that isn't psai" test "$(run "$h" >/dev/null 2>&1; echo $?)" = 1
h="$T/oldforeign"; mkdir -p "$h/.harness/skills/work" "$h/.claude/skills" "$T/elsewhere"; ln -s "$h/.harness/skills/work" "$h/.claude/skills/work"
run "$h" > /dev/null 2>&1
check "a foreign ~/.harness folder and links into it are left alone" bash -c "test -d '$h/.harness' && test ! -L '$h/.harness' && test \"\$(readlink '$h/.claude/skills/work')\" = '$h/.harness/skills/work' && test -d '$h/.psai/overlay'"
h="$T/oldlink"; mkdir -p "$h/.claude"; ln -s "$T/elsewhere" "$h/.harness"
run "$h" > /dev/null 2>&1
check "a ~/.harness link to something else is left alone" test "$(readlink "$h/.harness")" = "$T/elsewhere"

echo "L1 skills: registry, my-skills/, skills.yaml packs (local git, no network), adopt, ignore"
G="git -c user.email=t@t -c user.name=t"
sf="$T/skfork"; mkdir -p "$sf"; (cd "$ROOT" && git ls-files -co --exclude-standard -z | xargs -0 cp --parents -t "$sf" 2>/dev/null)
mkskill() { mkdir -p "$1"; printf -- '---\nname: %s\ndescription: "Test skill %s. Use when testing."\n---\nbody\n' "$(basename "$1")" "$(basename "$1")" > "$1/SKILL.md"; }
h="$T/skh"; ov="$h/.psai/overlay"; mkskill "$ov/my-skills/mine"   # the overlay holds your skills and skills.yaml
pk="$T/packsrc"; mkskill "$pk/skills/pk-tag"; mkskill "$pk/skills/pk-sha"
(cd "$pk" && git init -q -b main && git add -A && $G commit -qm one && git tag v1) || fail "pack fixture repo"
sha="$(git -C "$pk" rev-parse HEAD)"
printf 'skills:\n  - name: pk-tag\n    source: file://%s\n    path: skills/pk-tag\n    ref: v1\n  - name: pk-sha\n    source: file://%s\n    path: skills/pk-sha\n    ref: %s\nignore: [orca-cli]\n' "$pk" "$pk" "$sha" > "$ov/skills.yaml"
mkdir -p "$h/.claude/skills" "$h/.config/opencode/skills" "$h/.pi/agent/skills" "$h/.omp/agent/skills" "$h/.agents/skills" "$h/proj/.agents/skills" "$h/proj/.claude/skills"
mkskill "$h/.claude/skills/own-a"                                     # the user's own, in a tool folder
mkskill "$h/.config/opencode/skills/oc-only"; mkskill "$h/.pi/agent/skills/pi-only"; mkskill "$h/.omp/agent/skills/omp-only"
np="$T/npxsrc"; mkskill "$np/skills/npx-b"; (cd "$np" && git init -q -b main && git add -A && $G commit -qm one) || fail "npx fixture repo"
cp -r "$np/skills/npx-b" "$h/.agents/skills/npx-b"; ln -s ../../.agents/skills/npx-b "$h/.claude/skills/npx-b"   # as npx skills does
printf '{"version":3,"skills":{"npx-b":{"source":"%s","sourceType":"git","sourceUrl":"file://%s","skillPath":"skills/npx-b/SKILL.md"}}}\n' "$np" "$np" > "$h/.agents/.skill-lock.json"
mkskill "$h/.agents/skills/orca-cli"                                  # managed by another tool, ignored
mkskill "$h/proj/.agents/skills/proj-only"; ln -s ../../.agents/skills/proj-only "$h/proj/.claude/skills/proj-only"
srun() { env -u XDG_CONFIG_HOME -u PSAI_HOME -u PSAI_STATE HOME="$h" bash "$sf/install.sh" "$@"; }
sreg() { (cd "$h/proj" && env -u XDG_CONFIG_HOME -u PSAI_HOME -u PSAI_STATE HOME="$h" python3 "$sf/scripts/harness.py" skills --root "$h/.psai" --project "$h/proj" --json); }
q() { python3 -c "import json,sys; r=json.load(open('$T/reg.json')); sys.exit(0 if ($1) else 1)"; }
srun > "$T/sk.out" 2>&1 || { fail "install with skills"; cat "$T/sk.out"; }
check "the overlay's my-skills/mine linked into both folders" bash -c "test \"\$(readlink '$h/.claude/skills/mine')\" = '$h/.psai/overlay/my-skills/mine' && test -f '$h/.agents/skills/mine/SKILL.md'"
check "pack pinned to a tag fetched into state/skills-cache/nostack and linked" bash -c "test -f '$h/.psai/state/skills-cache/nostack/pk-tag/skills/pk-tag/SKILL.md' && test \"\$(readlink '$h/.claude/skills/pk-tag')\" = '$h/.psai/state/skills-cache/nostack/pk-tag/skills/pk-tag'"
check "pack pinned to a commit checked out at it" bash -c "test \"\$(git -C '$h/.psai/state/skills-cache/nostack/pk-sha' rev-parse HEAD)\" = '$sha' && test -f '$h/.agents/skills/pk-sha/SKILL.md'"
check "README-psai.md dropped in both folders" bash -c "grep -q 'psai adopt <name>' '$h/.claude/skills/README-psai.md' && grep -q 'customize-harness' '$h/.agents/skills/README-psai.md'"
check "unmanaged skills left in place" bash -c "test -d '$h/.claude/skills/own-a' -a ! -L '$h/.claude/skills/own-a' && test -d '$h/.agents/skills/npx-b'"
after="$(snap "$h")"; srun > /dev/null 2>&1
check "re-run with packs changes nothing" test "$after" = "$(snap "$h")"
(cd "$pk" && echo more >> skills/pk-tag/SKILL.md && $G commit -qam two)
srun > /dev/null 2>&1
check "a pinned pack ignores new upstream commits" bash -c "! grep -q more '$h/.claude/skills/pk-tag/SKILL.md'"
sreg > "$T/reg.json" || fail "registry"
check "registry: psai skill seen by all four tools" q "sorted(r['work']['tools']) == ['claude','omp','opencode','pi'] and not r['work']['unmanaged']"
check "registry: my-skills and packs are managed" q "not r['mine']['unmanaged'] and not r['pk-tag']['unmanaged'] and 'my-skills' in [l['kind'] for l in r['mine']['locations']]"
check "registry: tool-only folders map to their tool" q "r['oc-only']['tools'] == ['opencode'] and r['pi-only']['tools'] == ['pi'] and r['omp-only']['tools'] == ['omp']"
check "registry: unmanaged = own-a, npx-b and the tool-only ones" q "sorted(n for n in r if r[n]['unmanaged']) == ['npx-b','oc-only','omp-only','own-a','pi-only']"
check "registry: a link to the same copy is no duplicate" q "not r['npx-b']['duplicate'] and sorted(r['npx-b']['tools']) == ['claude','omp','opencode','pi']"
check "registry: project skills seen, not unmanaged" q "r['proj-only']['project_only'] and not r['proj-only']['unmanaged'] and 'claude' in r['proj-only']['tools']"
check "registry: ignored skill never reported" q "r['orca-cli']['ignored'] and not r['orca-cli']['unmanaged']"
check "check.sh-side count: 5 unmanaged" bash -c "cd '$h/proj' && HOME='$h' python3 '$sf/scripts/harness.py' skills check --root '$h/.psai' | grep -q 'info 5 unmanaged'"
check "nudge mentions the unmanaged count" bash -c "cd '$h/proj' && HOME='$h' python3 '$sf/scripts/harness.py' context '$h/.psai' | grep -q '^5 skill(s) in your tool folders'"
srun --adopt orca-cli > /dev/null 2>&1
check "adopt refuses an ignored skill" test -d "$h/.agents/skills/orca-cli" -a ! -L "$h/.agents/skills/orca-cli"
before="$(snap "$h")"; srun --adopt own-a --dry-run > /dev/null 2>&1
check "adopt --dry-run changes nothing" test "$before" = "$(snap "$h")" -a ! -e "$ov/my-skills/own-a"
srun --adopt own-a > "$T/adopt.out" 2>&1 || { fail "adopt own-a"; cat "$T/adopt.out"; }
check "adopt (own): moved into the overlay's my-skills/ and linked back to both folders" bash -c "test -f '$ov/my-skills/own-a/SKILL.md' && test \"\$(readlink '$h/.claude/skills/own-a')\" = '$h/.psai/overlay/my-skills/own-a' && test -L '$h/.agents/skills/own-a'"
srun --adopt npx-b > "$T/adopt.out" 2>&1 || { fail "adopt npx-b"; cat "$T/adopt.out"; }
check "adopt (pack): pinned skills.yaml entry from the npx lock" python3 -c "
import yaml,sys; e=[x for x in yaml.safe_load(open('$ov/skills.yaml'))['skills'] if x['name']=='npx-b']
sys.exit(0 if e and e[0]['source']=='file://$np' and e[0]['path']=='skills/npx-b' and e[0]['ref']=='$(git -C "$np" rev-parse HEAD)' else 1)"
check "adopt (pack): linked from the cache; old copy kept in the cache's .adopted/" bash -c "test \"\$(readlink '$h/.agents/skills/npx-b')\" = '$h/.psai/state/skills-cache/nostack/npx-b/skills/npx-b' && test -L '$h/.claude/skills/npx-b' && ls '$h/.psai/state/skills-cache/nostack/.adopted/' | grep -q '^npx-b-'"
check "adopt kept skills.yaml's other entries and ignore list" bash -c "grep -q 'name: pk-tag' '$ov/skills.yaml' && grep -q 'ignore: \[orca-cli\]' '$ov/skills.yaml'"
check "the overlay with adopted skills still validates" python3 -c "
import sys; sys.path.insert(0, '$sf/scripts'); import harness
sys.exit(1 if harness.validate('$ov') + harness.check_layout('$ov', '$sf/LAYOUT.md') else 0)"
check "my-skills/ and skills.yaml are user-owned" bash -c "cd '$sf' && test \"\$(printf 'my-skills/own-a/SKILL.md\nmy-skills/own-a/scripts/x.sh\nskills.yaml\nmy-skills/README.md\n' | python3 -c \"import sys; sys.path.insert(0, 'scripts'); import harness; print(' '.join(harness.user_files('.', 'LAYOUT.md', [l.strip() for l in sys.stdin])))\")\" = 'my-skills/own-a/SKILL.md my-skills/own-a/scripts/x.sh skills.yaml'"
printf 'skills:\n  - {name: pk-tag, source: "file://%s", path: skills/pk-tag, ref: v1}\nignore: [orca-cli]\n' "$pk" > "$ov/skills.yaml"; rm -rf "$ov/my-skills/mine"
srun > /dev/null 2>&1
check "removed entries and my-skills unlinked as stale" bash -c "test ! -L '$h/.claude/skills/pk-sha' && test ! -L '$h/.agents/skills/mine' && test ! -L '$h/.claude/skills/npx-b' && test -L '$h/.claude/skills/pk-tag'"
srun --uninstall > /dev/null 2>&1
check "uninstall removes skill links and README-psai.md, keeps unmanaged and the overlay's my-skills" bash -c "test -z \"\$(find '$h/.claude/skills' '$h/.agents/skills' -maxdepth 1 -lname '$h/.psai/*')\" && test ! -e '$h/.claude/skills/README-psai.md' && test -d '$h/.agents/skills/orca-cli' && test -f '$ov/my-skills/own-a/SKILL.md'"

echo "L1 PSAI_HOME overrides the link path"
h="$T/custom"; c="$h/tools/psai"; mkdir -p "$h/.pi/agent"
PSAI_HOME="$c" PSAI_STATE="$h/.psai-state" env -u XDG_CONFIG_HOME HOME="$h" bash "$I" > /dev/null 2>&1
check "the home made at \$PSAI_HOME, not ~/.psai" bash -c "test \"\$(readlink '$c/framework')\" = '$ROOT' && test ! -e '$h/.psai'"
check "skills and pi extension point through \$PSAI_HOME" bash -c "test \"\$(readlink '$h/.agents/skills/work')\" = '$c/framework/skills/work' && test \"\$(readlink '$h/.pi/agent/extensions/psai.ts')\" = '$c/framework/plugins/pi/psai.ts'"
check "nudge shows \$PSAI_HOME paths" bash -c "PSAI_HOME='$c' HOME='$h' bash '$ROOT/plugins/claude/hooks/session-start.sh' | grep -Fq 'python3 $c/framework/scripts/psai.py'"
PSAI_HOME="$c" PSAI_STATE="$h/.psai-state" env -u XDG_CONFIG_HOME HOME="$h" bash "$I" --uninstall > /dev/null 2>&1
check "uninstall removes the framework link and its links" bash -c "test ! -L '$c/framework' && test ! -L '$h/.agents/skills/work' && test ! -L '$h/.pi/agent/extensions/psai.ts'"

echo "L1 owner rules reach the nudge"
fk="$T/ownerfork"; cp -r "$ROOT" "$fk"; rm -rf "$fk/.git"; echo "- Ask before deleting anything." > "$fk/instructions/owner.md"
check "nudge includes owner.md" bash -c "python3 '$fk/scripts/harness.py' context '$fk' | grep -q 'Ask before deleting anything'"

echo "L1 a fork takes upstream updates without conflicts"
G="git -c user.email=t@t -c user.name=t"
up="$T/upstream"; mkdir -p "$up"
(cd "$ROOT" && git ls-files -co --exclude-standard -z | xargs -0 cp --parents -t "$up" 2>/dev/null)
(cd "$up" && git init -q -b main && git add -A && $G commit -qm upstream) || fail "upstream repo"
git clone -q "$up" "$T/fork"; f="$T/fork"
if [ -n "$FIX" ]; then cp -r "$FIX"/workflows "$FIX"/steps "$FIX"/roles "$FIX"/guides "$FIX"/templates "$FIX"/knowledge "$FIX"/my-skills "$f/"; rm -f "$f"/*/README.md.fix; fi
# the fixture's folders have no READMEs of their own, so the fork keeps upstream's
echo "- Ask before deleting anything." > "$f/instructions/owner.md"
mkdir -p "$f/my-skills/my-notes"; printf -- '---\nname: my-notes\ndescription: "Notes. Use when noting."\n---\n' > "$f/my-skills/my-notes/SKILL.md"
printf 'skills:\n  - {name: pk, source: github:o/r, path: pk, ref: v1}\nignore: [orca-cli]\n' > "$f/skills.yaml"
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
check "the fork's my-skills/ and skills.yaml count as user files" bash -c "grep -q 'my-skills/my-notes/SKILL.md' <<< '$user_before' && grep -q 'skills.yaml' <<< '$user_before'"
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
  fi
  cd "$ROOT" || exit 1
fi

echo
if [ "$fails" = 0 ]; then echo "check: all passed"; else echo "check: $fails failed"; exit 1; fi
