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
echo "L1 psai build --standalone: Agent Plugins, pi, omp, opencode"
check "every target is built by default" bash -c "for t in claude agent-plugins pi omp opencode; do test -f '$S/dist/example/'\$t/bundle.yaml || exit 1; done"
A="$S/dist/example/agent-plugins"
check "agent-plugins: .cursor-plugin/plugin.json (name, version, skills, rules) and a marketplace" python3 -c "
import json,sys; m=json.load(open('$A/.cursor-plugin/plugin.json')); k=json.load(open('$S/dist/example/.cursor-plugin/marketplace.json'))
sys.exit(0 if m['name']=='example' and m['version']=='1.0.0' and m['skills']=='./skills/' and m['rules']=='./rules/' and k['plugins'][0]['source']=='./agent-plugins' else 1)"
check "agent-plugins: the nudge as an always-applied rule, and the skills" bash -c "grep -q '^alwaysApply: true' '$A/rules/psai.mdc' && grep -q -- '^- example:example: ' '$A/rules/psai.mdc' && test -f '$A/skills/work/SKILL.md'"
check "pi: a package.json with the pi manifest, the extension and the skills" python3 -c "
import json,os,sys; m=json.load(open('$S/dist/example/pi/package.json'))['pi']
sys.exit(0 if m=={'extensions': ['./extensions/psai.ts'], 'skills': ['./skills']} and os.path.isfile('$S/dist/example/pi/skills/change-notes/SKILL.md') else 1)"
check "omp: a package.json with the omp manifest" python3 -c "import json,sys; m=json.load(open('$S/dist/example/omp/package.json'))['omp']; sys.exit(0 if m['extensions']==['./extensions/psai.ts'] else 1)"
check "the bundled extensions point their one bootstrap at the bundle" bash -c "for f in '$S/dist/example/pi/extensions/psai.ts' '$S/dist/example/omp/extensions/psai.ts' '$S/dist/example/opencode/plugin/psai.js'; do grep -q 'new URL(\".\", import.meta.url)), \"..\"); // psai-bootstrap' \"\$f\" && ! grep -q 'PSAI_HOME ||' \"\$f\" || exit 1; done"
if command -v node >/dev/null; then
  cat > "$T/t.mjs" <<'JS'
const [, , pi, omp, oc] = process.argv;
const ok = [];
for (const [name, p] of [["pi", pi], ["omp", omp]]) {
  const h = {}; (await import(p)).default({ on: (e, f) => (h[e] = f) });
  const r = await h.before_agent_start({ systemPrompt: name === "omp" ? [] : "base" }, { agent: { kind: "main" } });
  const s = Array.isArray(r.systemPrompt) ? r.systemPrompt.join("\n") : r.systemPrompt;
  if (s.includes("- example:example:")) ok.push(name);
}
const { Psai } = await import(oc);
const hooks = await Psai({ client: { session: { get: async () => ({ data: {} }) } } });
const out = { system: [] }; await hooks["experimental.chat.system.transform"]({ sessionID: "x" }, out);
if (out.system.join("").includes("- example:example:")) ok.push("opencode");
console.log(ok.join(" "));
JS
  r="$(cd "$T" && env -u PSAI_HOME HOME="$T/n" node "$T/t.mjs" "$S/dist/example/pi/extensions/psai.ts" "$S/dist/example/omp/extensions/psai.ts" "$S/dist/example/opencode/plugin/psai.js" 2>/dev/null)"
  check "pi, omp and opencode extensions inject the nudge from their bundle" test "$r" = "pi omp opencode"
else echo "  skip node not installed (bundled extensions)"; fi
O="$S/dist/example/opencode"; oh="$T/oh"; mkdir -p "$oh/.config/opencode"
before="$(cd "$oh" && find . | sort)"; HOME="$oh" bash "$O/install.sh" --dry-run > /dev/null 2>&1
check "opencode install.sh --dry-run changes nothing" test "$before" = "$(cd "$oh" && find . | sort)"
HOME="$oh" bash "$O/install.sh" > /dev/null 2>&1
check "opencode install.sh: the stub plugin and the skill links" bash -c "grep -q '$O/plugin/psai.js' '$oh/.config/opencode/plugin/psai-example.js' && test \"\$(readlink '$oh/.config/opencode/skills/work')\" = '$O/skills/work'"
after="$(cd "$oh" && find . -printf '%p %l\n' | sort)"; HOME="$oh" bash "$O/install.sh" > /dev/null 2>&1
check "opencode install.sh is idempotent" test "$after" = "$(cd "$oh" && find . -printf '%p %l\n' | sort)"
if [ "${PSAI_DISCOVER:-0}" = 1 ]; then  # the real tools load the packages (check.sh --discover)
  w="$T/w"; mkdir -p "$w" "$T/ph/.pi/agent" "$T/mh/.omp/agent"
  if command -v pi >/dev/null; then
    o="$(cd "$w" && echo '{"type":"get_commands"}' | HOME="$T/ph" timeout 60 pi --mode rpc --no-session --offline -e "$S/dist/example/pi" 2>/dev/null)"
    check "pi loads the package's skills" bash -c 'grep -q "skill:work\"" <<< "$1" && grep -q "skill:change-notes\"" <<< "$1"' _ "$o"
  fi
  if command -v omp >/dev/null; then
    o="$(cd "$w" && (echo '{"type":"get_state"}'; sleep 10) | HOME="$T/mh" ANTHROPIC_API_KEY=dummy timeout 90 omp --mode rpc --no-session --no-title --plugin-dir "$S/dist/example/omp" 2>/dev/null)"
    check "omp loads the plugin's skills" bash -c 'grep -q "skill:work\"" <<< "$1" && grep -q "skill:change-notes\"" <<< "$1"' _ "$o"
  fi
  if command -v opencode >/dev/null; then
    o="$(cd "$w" && HOME="$oh" XDG_CONFIG_HOME="$oh/.config" XDG_DATA_HOME="$oh/.d" XDG_CACHE_HOME="$oh/.c" XDG_STATE_HOME="$oh/.s" timeout 120 opencode debug skill --pure 2>/dev/null)"
    check "opencode sees the installed skills" bash -c 'grep -q "\"name\": \"work\"" <<< "$1" && grep -q "\"name\": \"change-notes\"" <<< "$1"' _ "$o"
  fi
fi
HOME="$oh" bash "$O/install.sh" --uninstall > /dev/null 2>&1
check "opencode install.sh --uninstall removes only its stub and links" bash -c "test ! -e '$oh/.config/opencode/plugin/psai-example.js' && test -z \"\$(ls -A '$oh/.config/opencode/skills')\""
check "an unknown target is refused" bash -c "$(declare -f P); T='$T' ROOT='$ROOT'; ! P build --standalone '$S' --target vscode"
exit $((fails > 0))
