#!/usr/bin/env bash
# L1 tests for `psai build --standalone` (ADR 0011, section 13): the package per target, the bundle as a psai home
# (its nudge through the target's hooks, psai finding the bundle, stack management refused), determinism and --check.
# Temp folders, no network, no AI. Prints "  ok   ..." / "  FAIL ..." (check.sh runs it).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
FX="$ROOT/evals/fixtures/stacks/example"
[ -d "$FX" ] || exit 0
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
unset PSAI_HOME PSAI_STATE PSAI_TRACE PSAI_ROLE PSAI_EVAL
fails=0
pass() { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; fails=$((fails + 1)); }
check() { local msg="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$msg"; else fail "$msg"; fi; }
S="$T/example"; cp -r "$FX" "$S"; (cd "$S" && git init -q -b main && git add -A && git -c user.name=t -c user.email=t@t commit -qm one)
P() { (cd "$T" && HOME="$T" python3 "$ROOT/scripts/psai.py" "$@"); }

echo "L1 psai build --standalone: Claude Code"
P build --standalone "$S" > "$T/b.out" 2>&1 || { fail "build"; cat "$T/b.out"; }
B="$S/dist/example/claude"
check "the plugin: plugin.json with the stack's name and version, hooks, skills" bash -c "python3 -c \"import json,sys; m=json.load(open('$B/.claude-plugin/plugin.json')); sys.exit(0 if m['name']=='example' and m['version']=='1.0.0' else 1)\" && test -f '$B/hooks/hooks.json' -a -f '$B/hooks/session-start.sh' && test -f '$B/skills/work/SKILL.md' -a -f '$B/skills/request-router/SKILL.md' -a -f '$B/skills/change-notes/SKILL.md'"
check "a marketplace next to it" python3 -c "import json,sys; m=json.load(open('$S/dist/example/.claude-plugin/marketplace.json')); sys.exit(0 if m['plugins'][0]['source']=='./claude' and m['name']=='example' else 1)"
check "the bundle is a psai home: the framework at this version, the stack, bundle.yaml" bash -c "test -f '$B/framework/scripts/psai.py' && test \"\$(cat '$B/framework/VERSION')\" = \"\$(cat '$ROOT/VERSION')\" && test -f '$B/stacks/example/workflows/example.yaml' && grep -q 'standalone: true' '$B/bundle.yaml'"
check "nothing of the framework's own tests or the stack's dist/ inside" bash -c "test ! -e '$B/framework/evals' && test ! -e '$B/stacks/example/dist' && test ! -e '$B/framework/scripts/__pycache__'"
cp -r "$S/dist" "$T/dist1"; P build --standalone "$S" > /dev/null 2>&1
check "building twice gives the same tree" diff -r "$T/dist1" "$S/dist"
check "--check passes on a fresh dist/" bash -c "$(declare -f P); T='$T' ROOT='$ROOT'; P build --standalone '$S' --check"
echo "- a new rule" >> "$S/guides/example-rules.md"
check "--check fails on a stale dist/" bash -c "$(declare -f P); T='$T' ROOT='$ROOT'; ! P build --standalone '$S' --check"
hook() { python3 -c "import json,sys; print(json.load(open('$B/hooks/hooks.json'))['hooks'][sys.argv[1]][0]['hooks'][0]['command'])" "$1"; }
out="$(cd "$T" && env -u PSAI_HOME HOME="$T/u" CLAUDE_PLUGIN_ROOT="$B" bash -c "$(hook SessionStart)" < /dev/null)"
check "the SessionStart hook injects the nudge from the bundle" python3 -c "import json,sys; c=json.loads(sys.argv[1])['hookSpecificOutput']['additionalContext']; sys.exit(0 if '- example:example: ' in c and sys.argv[2] in c else 1)" "$out" "$B/framework/scripts/psai.py"
check "the overlay is created in the bundle on first use" bash -c "test -f '$B/overlay/stack.yaml' && git -C '$B/overlay' rev-parse HEAD"
out="$(cd "$T" && env -u PSAI_HOME HOME="$T/u" CLAUDE_PLUGIN_ROOT="$B" bash -c "$(hook SubagentStart)" < /dev/null)"
check "a subagent gets the role-mode nudge" grep -q 'Role mode' <<< "$out"
check "psai in the bundle finds the bundle without PSAI_HOME" bash -c "cd '$T' && env -u PSAI_HOME HOME='$T/u' python3 '$B/framework/scripts/psai.py' route | grep -q '^- example:example: '"
check "stack management is disabled in a bundle" bash -c "cd '$T' && ! env -u PSAI_HOME HOME='$T/u' python3 '$B/framework/scripts/psai.py' stack add '$S' --yes"
check "the engine runs in the bundle (psai node)" bash -c "cd '$T' && env -u PSAI_HOME HOME='$T/u' python3 '$B/framework/scripts/psai.py' node example:example do | grep -q '^  brief: $B/stacks/example/roles/doer.md'"
if command -v claude >/dev/null; then
  check "claude plugin validate accepts the plugin and the marketplace" bash -c "claude plugin validate '$B' && claude plugin validate '$S/dist/example'"
else echo "  skip claude CLI not found (plugin validate)"; fi
check "an unknown target is refused" bash -c "$(declare -f P); T='$T' ROOT='$ROOT'; ! P build --standalone '$S' --target vscode"
exit $((fails > 0))
