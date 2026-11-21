#!/usr/bin/env bash
# L0 tests for psai resolve and stack.yaml (ADR 0011, section 5), against the fixture stacks in a temp PSAI_HOME.
# No AI, no network, never the real HOME. Prints "  ok   ..." / "  FAIL ..." lines (check.sh runs it).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
FIX="$ROOT/evals/fixtures/harness-content"; FS="$ROOT/evals/fixtures/stacks"
fails=0
pass() { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; fails=$((fails + 1)); }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
H="$T/home"; mkdir -p "$H/stacks"
ln -s "$ROOT" "$H/framework"; ln -s "$FIX" "$H/stacks/example"
cp -r "$FS/other" "$H/stacks/other"; cp -r "$FS/nostack" "$H/overlay"
R() { PSAI_HOME="$H" python3 "$ROOT/scripts/resolve.py" "$@" 2>/dev/null; }
is() { # message, expected stdout, args...
  local msg="$1" want="$2"; shift 2; local got; got="$(R "$@")"
  [ "$got" = "$want" ] && pass "$msg" || fail "$msg (got: $got)"
}
code() { # message, expected exit code, args...
  local msg="$1" want="$2"; shift 2; R "$@" >/dev/null; local rc=$?
  [ "$rc" = "$want" ] && pass "$msg" || fail "$msg (exit $rc, want $want)"
}
S="$H/stacks"; O="$H/overlay"
is "workflow by stack:name" "$S/example/workflows/example.yaml" workflow example:example
is "kind taken from the path" "$S/other/workflows/triage.yaml" other:workflows/triage.yaml
is "bare name, no --from: the one stack that has it" "$S/other/workflows/triage.yaml" workflow triage
is "role short form" "$S/example/roles/doer.md" role example:doer
is "--from makes a bare ref stack-local" "$S/other/guides/private.md" --from other guide guides/private.md
is "the overlay's override wins" "$O/overrides/example/guides/example-rules.md" guide example:example-rules
is "--all lists override then original" "$(printf '%s\n%s' "$O/overrides/example/guides/example-rules.md" "$S/example/guides/example-rules.md")" --all guide example:example-rules
is "a cross-stack read of an exported guide" "$O/overrides/example/guides/example-rules.md" --from other file example:guides/example-rules.md
code "not found: exit 3" 3 role example:ghost
code "unknown stack: exit 3" 3 role ghost:doer
code "a private name across stacks: exit 4" 4 --from example guide other:private
code "the overlay may reference private names" 0 --from nostack guide other:private
code "the framework's files are always reachable" 0 --from other file psai:skills/work/escalation.md
is "knowledge is additive: stack's, then the overlay's" "$(printf '%s\n%s' "$S/example/knowledge/roles/doer/INDEX.md" "$O/knowledge/example/roles/doer/INDEX.md")" --all knowledge example:roles/doer/INDEX.md
is "skill: this stack's copy first" "$S/other/my-skills/change-notes/SKILL.md" --from other skill change-notes
is "skill: another stack's copy for its own refs" "$S/example/my-skills/change-notes/SKILL.md" --from example skill change-notes
is "skill: the overlay's own" "$O/my-skills/mine/SKILL.md" --from example skill mine
is "skill: framework names first" "$H/framework/skills/work/SKILL.md" --from other skill work
code "skill: two stacks at the same level: exit 5" 5 skill change-notes
code "skill: another stack's unexported skill: exit 4" 4 --from example skill other:change-notes
is "--write: an inbox goes to the overlay" "$O/knowledge/example/roles/doer/inbox.md" --write knowledge example:roles/doer/inbox.md
is "--write: a pinned stack's file becomes an override" "$O/overrides/example/guides/new.md" --write guide example:new
is "--write: a dev stack's file goes to its clone" "$S/other/guides/new.md" --write guide other:new
is "--write: the overlay's own file" "$O/roles/mine.md" --write role nostack:mine
code "--write: the framework is read-only (exit 4)" 4 --write file psai:skills/work/SKILL.md
j="$(R --json role example:doer)"
python3 -c "import json,sys; d=json.loads(sys.argv[1]); sys.exit(0 if d['stack']=='example' and d['layer']=='example' and d['exported'] and d['overridden_by'] is None else 1)" "$j" \
  && pass "--json: stack, layer, exported, overridden_by" || fail "--json ($j)"
# single-root compat mode: a home with no framework/ is the stack nostack
c="$(PSAI_HOME="$FIX" python3 "$ROOT/scripts/resolve.py" --json role doer 2>/dev/null)"
python3 -c "import json,sys; d=json.loads(sys.argv[1]); sys.exit(0 if d['stack']=='nostack' and d['path']=='$FIX/roles/doer.md' else 1)" "$c" \
  && pass "compat: a single root is the stack nostack" || fail "compat ($c)"
[ "$(PSAI_HOME="$FIX" python3 "$ROOT/scripts/resolve.py" skill change-notes 2>/dev/null)" = "$FIX/my-skills/change-notes/SKILL.md" ] \
  && pass "compat: skills from the root's my-skills/" || fail "compat skills"
[ "$(PSAI_HOME="$H" python3 "$ROOT/scripts/psai.py" resolve role example:doer 2>/dev/null)" = "$S/example/roles/doer.md" ] \
  && pass "psai resolve runs resolve.py" || fail "psai resolve"

# stack.yaml
sv() { python3 -c "
import sys, yaml; sys.path.insert(0, '$ROOT/scripts'); import resolve
m = yaml.safe_load(sys.argv[1]); errs = resolve.validate_stack(m, overlay=sys.argv[2] == 'overlay')
print('\n'.join(errs)); sys.exit(1 if errs else 0)" "$@"; }
for s in "$FIX" "$FS/other"; do sv "$(cat "$s/stack.yaml")" stack >/dev/null && pass "stack.yaml valid: $(basename "$s")" || fail "stack.yaml: $s"; done
sv "$(cat "$FS/nostack/stack.yaml")" overlay >/dev/null && pass "stack.yaml valid: the overlay" || fail "overlay stack.yaml"
bad() { local out; out="$(sv "$2" "${3:-stack}")" && fail "rejects: $1" || { grep -q "$4" <<< "$out" && pass "rejects: $1" || fail "rejects: $1 (said: $out)"; }; }
base='schema: 1
name: acme
version: 1.0.0
description: "x"
psai: ">=2.1 <4"'
bad "missing fields" 'name: acme' stack 'missing version'
bad "a bad version range" "${base/>=2.1 <4/three or later}" stack 'bad version range'
bad "a reserved name" "${base/name: acme/name: psai}" stack 'reserved'
bad "a bad name" "${base/name: acme/name: Acme_1}" stack "doesn't match"
bad "an unknown key" "$base
colour: red" stack 'unknown key'
bad "overlay-only keys in a stack" "$base
disable: [x:y]" stack 'only the overlay'
bad "a long description" "${base/\"x\"/\"$(printf 'w %.0s' $(seq 30))\"}" stack 'over 25 words'
bad "exports that aren't a list or *" "$base
exports: {roles: all}" stack 'allowed form'
python3 -c "
import sys; sys.path.insert(0, '$ROOT/scripts'); import resolve as r
ok = r.in_range('3.0.0', '>=3.0 <4') and not r.in_range('4.0.0', '>=3.0 <4') and r.in_range('2.1.0', '^2.1') \
  and not r.in_range('3.0.0', '^2.1') and r.in_range('1.4.2', '~1.4') and not r.in_range('1.5.0', '~1.4')
sys.exit(0 if ok else 1)" && pass "version ranges (>=, <, ^, ~)" || fail "version ranges"
exit $((fails > 0))
