#!/usr/bin/env bash
# L0 tests for the model per role (ADR 0011, section 8): the order of sources, tiers mapped per tool, concrete ids,
# validation, `psai node`'s model line and `psai setup models`. Fixture stacks in a temp PSAI_HOME; no AI, no network.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
FIX="$ROOT/evals/fixtures/stacks/example"; FS="$ROOT/evals/fixtures/stacks"
[ -d "$FIX" ] || exit 0
fails=0
pass() { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; fails=$((fails + 1)); }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
unset PSAI_STATE PSAI_TRACE PSAI_ROLE PSAI_EVAL
H="$T/home"; mkdir -p "$H/stacks"; ln -s "$ROOT" "$H/framework"; cp -r "$FIX" "$H/stacks/example"; cp -r "$FS/other" "$H/stacks/other"; cp -r "$FS/nostack" "$H/overlay"
M() { (cd "$T" && PSAI_HOME="$H" HOME="$T" python3 "$ROOT/scripts/psai.py" resolve model "$@" 2>/dev/null); }
is() { local msg="$1" want="$2"; shift 2; local got; got="$(M "$@")"; [ "$got" = "$want" ] && pass "$msg" || fail "$msg (got: $got)"; }
is "none set: the tool's current model (nothing passed)" "" example:doer
printf 'models:\n  default: balanced\n  roles: {doer: fast}\n' >> "$H/stacks/example/stack.yaml"
is "stack.yaml models.default" "sonnet" example:checker
is "stack.yaml models.roles.<role> beats the default" "haiku" example:doer
sed -i 's/^may_change: anything/may_change: anything\nmodel: strong/' "$H/stacks/example/roles/doer.md"
is "the role's frontmatter beats the stack's roles" "opus" example:doer
is "a tier maps per tool (pi)" "claude-opus-5-5" example:doer --tool pi
is "opencode's id, but not settable per call" "anthropic/claude-opus-5-5  (not settable per call in opencode)" example:doer --tool opencode
printf 'models:\n  roles:\n    "example:doer": {claude: sonnet}\n' >> "$H/overlay/stack.yaml"
is "the overlay's models.roles[stack:role] wins" "sonnet" example:doer
is "a mapping without this tool counts as unset: the next source answers" "claude-opus-5-5" example:doer --tool pi
(cd "$T" && PSAI_HOME="$H" HOME="$T" python3 "$ROOT/scripts/psai.py" setup models --set pi.strong=my-opus) > "$T/setup.out" 2>&1
grep -q '^omp: .*(not settable per call)' "$T/setup.out" && pass "setup models prints the map per tool" || fail "setup models output"
is "the overlay's tiers map changes the id" "my-opus" example:doer --tool pi
python3 -c "import yaml,sys; m=yaml.safe_load(open('$H/overlay/stack.yaml'))['models']; sys.exit(0 if m['tiers']['claude']['fast']=='haiku' and m['roles']['example:doer']=={'claude':'sonnet'} else 1)" \
  && pass "setup models writes every tier and keeps your roles" || fail "setup models wrote the wrong thing"
n="$(cd "$T" && PSAI_HOME="$H" HOME="$T" python3 "$ROOT/scripts/psai.py" node example:example do 2>/dev/null)"
grep -q "^  model: claude sonnet; pi my-opus (tier strong); opencode, omp: not settable per call (say so in the final report)$" <<< "$n" && pass "psai node prints the role's model line" || fail "psai node model line: $(grep model: <<< "$n")"
n="$(cd "$T" && PSAI_HOME="$H" HOME="$T" python3 "$ROOT/scripts/psai.py" node example:example check 2>/dev/null)"
grep -q "^  model: claude sonnet (tier balanced); pi claude-sonnet-5-5 (tier balanced); opencode, omp: not settable per call" <<< "$n" && pass "psai node: tiers, with opencode and omp not settable per call" || fail "psai node tier line: $(grep model: <<< "$n")"
val() { PSAI_HOME="$H" python3 -c "
import sys; sys.path.insert(0, '$ROOT/scripts'); import harness; e = harness.validate(sys.argv[1]); print('\n'.join(e))" "$1"; }
sed -i 's/^model: strong/model: huge/' "$H/stacks/example/roles/doer.md"
grep -q "roles/doer.md: model: 'huge' is not a tier" <<< "$(val "$H/stacks/example")" && pass "validate: rejects a role's unknown tier" || fail "validate role model"
sed -i 's/^model: huge/model: {claude: opus, emacs: x}/' "$H/stacks/example/roles/doer.md"
grep -q "unknown tool 'emacs'" <<< "$(val "$H/stacks/example")" && pass "validate: rejects an unknown tool in a mapping" || fail "validate role model mapping"
python3 -c "
import sys, yaml; sys.path.insert(0, '$ROOT/scripts'); import resolve
m = yaml.safe_load(open('$FIX/stack.yaml')); m['models'] = {'default': 'turbo'}
e = resolve.validate_stack(m); sys.exit(0 if any('not a tier' in x for x in e) else 1)" && pass "stack.yaml: rejects an unknown tier" || fail "stack.yaml model validation"
exit $((fails > 0))
