#!/usr/bin/env bash
# L0 tests for routing across stacks (ADR 0011, section 4): the merged index, the namespaced nudge and its word
# budget, prefer/priority/disable, stack rules, the cache, and stack:workflow in the trace and the ledger.
# Fixture stacks in a temp PSAI_HOME; no AI, no network. Prints "  ok   ..." / "  FAIL ..." (check.sh runs it).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
FIX="$ROOT/evals/fixtures/harness-content"; FS="$ROOT/evals/fixtures/stacks"
[ -d "$FIX" ] || exit 0
fails=0
pass() { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; fails=$((fails + 1)); }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
unset PSAI_STATE PSAI_TRACE PSAI_ROLE PSAI_EVAL
mkhome() { # dir -> a home with example (pinned), other, and the fixture overlay
  mkdir -p "$1/stacks"; ln -s "$ROOT" "$1/framework"; cp -r "$FIX" "$1/stacks/example"; cp -r "$FS/other" "$1/stacks/other"
  cp -r "$FS/nostack" "$1/overlay"
}
H="$T/home"; mkhome "$H"
ctx() { (cd "$T" && PSAI_HOME="$1" HOME="$T" python3 "$ROOT/scripts/harness.py" context "$1" '~/.psai'); }
route() { (cd "$T" && PSAI_HOME="$1" HOME="$T" python3 "$ROOT/scripts/psai.py" route); }
wwords() { python3 -c "import sys; print(sum(len(l.split()) for l in sys.stdin if l.startswith('- ')))"; }
has() { grep -q -- "$2" <<< "$1"; }
ok() { if "$@"; then pass "$msg"; else fail "$msg"; fi; }
at() { grep -n -- "$2" <<< "$1" | head -1 | cut -d: -f1; }
before() { local a b; a="$(at "$1" "$2")"; b="$(at "$1" "$3")"; [ -n "$a" ] && [ -n "$b" ] && [ "$a" -lt "$b" ]; }
hasnt() { ! grep -q -- "$2" <<< "$1"; }

n="$(ctx "$H")"
msg="nudge: workflows as stack:name, by priority (example 50, then other 40)"; ok before "$n" '^- example:example: ' '^- other:triage: '
msg="nudge: deterministic"; ok test "$n" = "$(ctx "$H")"
msg="nudge: a stack's instructions/stack.md as its rules"; ok has "$n" '^## other rules'
msg="nudge: the fixture stacks fit the 300-word workflow budget"; ok test "$(printf '%s\n' "$n" | sed -n '/^Workflows:/,/^$/p' | wwords)" -le 300
r="$(route "$H")"
msg="route: tie-break rules, stacks by priority, qualified tree leaves"; ok eval 'has "$r" "prefer rules first" && has "$r" "^## example (priority 50)" && has "$r" "workflow: example:example"'

# priority, disable and prefer from the overlay's stack.yaml
H2="$T/h2"; mkhome "$H2"
printf 'priority: {other: 90}\nprefer:\n  - {if: "a note to sort", use: other:triage}\n' >> "$H2/overlay/stack.yaml"
n="$(ctx "$H2")"; r="$(route "$H2")"
msg="priority: the overlay raises other above example"; ok eval 'before "$n" "^- other:triage: " "^- example:example: " && has "$r" "^## other (priority 90)"'
msg="prefer: listed in route"; ok has "$r" '^- prefer: if a note to sort -> other:triage'
printf 'disable: [other:triage]\n' >> "$H2/overlay/stack.yaml"
msg="disable a workflow: gone from the nudge and route"; ok bash -c "! grep -q 'other:triage' <<< \"\$(cd '$T' && PSAI_HOME='$H2' HOME='$T' python3 '$ROOT/scripts/harness.py' context '$H2')\" && grep -q '^- disabled: other:triage' <<< \"\$(cd '$T' && PSAI_HOME='$H2' HOME='$T' python3 '$ROOT/scripts/psai.py' route)\""
sed -i 's/^disable: .*/disable: [example]/' "$H2/overlay/stack.yaml"
msg="disable a stack: none of its workflows"; ok bash -c "! grep -q -- '- example:' <<< \"\$(cd '$T' && PSAI_HOME='$H2' HOME='$T' python3 '$ROOT/scripts/harness.py' context '$H2')\""

# the budget: a big low-priority stack collapses to one line; the overlay never does
H3="$T/h3"; mkhome "$H3"; B="$H3/stacks/big"; mkdir -p "$B/workflows"
printf 'schema: 1\nname: big\nversion: 1.0.0\ndescription: "Forty chores."\npsai: ">=2.1 <4"\nrouting: {priority: 10}\n' > "$B/stack.yaml"
for i in $(seq 1 40); do printf 'name: w%s\nwhen: Chore number %s for the weekly cleanup of old files.\nstart: a\nnodes: {a: {terminal: true}}\n' "$i" "$i" > "$B/workflows/w$i.yaml"; done
mkdir -p "$B/instructions"; echo "Big rules." > "$B/instructions/stack.md"
printf '  - { name: big, source: "github:x/big", ref: v1.0.0, mode: pinned }\n' >> "$H3/overlay/stacks.yaml"
n="$(ctx "$H3")"
msg="over budget: the lowest-priority stack collapses to one line"; ok eval 'has "$n" "^- big (40 workflows): Forty chores." && hasnt "$n" "^- big:w1: " && has "$n" "^- example:example: " && has "$n" "psai route"'
msg="a collapsed stack's rules aren't injected"; ok hasnt "$n" 'Big rules'
msg="collapsed, the workflow lines fit the budget"; ok test "$(printf '%s\n' "$n" | sed -n '/^Workflows:/,/^$/p' | wwords)" -le 300
msg="route still lists every workflow of a collapsed stack"; ok has "$(route "$H3")" '^- big:w40: '
mv "$B/workflows"/* "$H3/overlay/workflows/" 2>/dev/null || { mkdir -p "$H3/overlay/workflows"; mv "$B/workflows"/* "$H3/overlay/workflows/"; }
msg="the overlay's own workflows are never collapsed"; ok has "$(ctx "$H3")" '^- nostack:w40: '

# the stack rules cap, the cache, the trace and the ledger
H4="$T/h4"; mkhome "$H4"; printf '%s ' $(seq 1 80) > "$H4/stacks/other/instructions/stack.md"
msg="a stack's rules are capped at 60 words"; ok bash -c "grep -A1 '^## other rules' <<< \"\$(cd '$T' && PSAI_HOME='$H4' HOME='$T' python3 '$ROOT/scripts/harness.py' context '$H4')\" | tail -1 | grep -q '^1 2 .* 60 \.\.\.$'"
(cd "$T" && PSAI_HOME="$H" python3 "$ROOT/scripts/psai.py" index) > /dev/null
msg="psai index caches the index in state/"; ok test -f "$H/state/index.json"
sed -i 's/^when: .*/when: Sorting incoming notes, changed./' "$H/stacks/other/workflows/triage.yaml"
msg="a changed workflow rebuilds the cached index"; ok has "$(route "$H")" '^- other:triage: Sorting incoming notes, changed.'
g="$T/repo"; mkdir -p "$g"; (cd "$g" && git init -q)
(cd "$g" && PSAI_HOME="$H" bash "$ROOT/skills/work/trace.sh" triage sort) > /dev/null 2>&1
msg="the trace names a run stack:workflow, even when called with a bare name"; ok grep -qx 'workflow other:triage' "$g/.git/psai-trace"
(cd "$g" && PSAI_HOME="$H" PSAI_STATE="$T/st" python3 "$ROOT/scripts/ledger.py" start --tool claude --id s1 --project "$g") > /dev/null
(cd "$g" && PSAI_HOME="$H" PSAI_STATE="$T/st" python3 "$ROOT/scripts/ledger.py" workflow other:triage --id s1) > /dev/null
msg="the ledger records the stacks' versions and workflows as stack:name"; ok python3 -c "
import json; r = json.load(open('$T/st/sessions/s1.json'))
assert r['stacks'] == {'example': '1.0.0', 'other': '0.2.0'}, r['stacks']
assert r['workflows'] == ['other:triage'], r['workflows']"
exit $((fails > 0))
