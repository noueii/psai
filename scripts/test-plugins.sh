#!/usr/bin/env bash
# Prove, without AI and without network, that each tool's psai plugin puts the live nudge into the session.
# Each tool runs in a temp HOME with our plugin plus a test-only capture plugin that records the final system
# prompt; the model call then fails against a closed local port. Claude Code's hook is run directly.
# Usage: scripts/test-plugins.sh   (prints "ok"/"FAIL"/"skip" lines; exits 1 on any failure)
# Each tool runs with stdin closed: with an open stdin it waits on it and the test times out.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
fails=0
res() { if [ "$2" = 0 ]; then echo "  ok   $1"; else echo "  FAIL $1"; fails=$((fails + 1)); fi; }
skip() { echo "  skip $1"; }
WANT='run the request-router skill first'
ROLEWANT='Do not run request-router or work'
# role mode: the capture has the role text and not the routing line
role_ok() { grep -Fq "$ROLEWANT" "$1" 2>/dev/null && ! grep -Fq "$WANT" "$1"; }
NL='String.fromCharCode(10)'

# Claude Code: run the SessionStart hook as the plugin would.
mkdir -p "$T/claude"; ln -s "$ROOT" "$T/claude/.psai"
out="$(env -u PSAI_HOME -u PSAI_ROLE HOME="$T/claude" bash "$ROOT/plugins/claude/hooks/session-start.sh")"
ctx="$(cd "$T" && HOME="$T/claude" python3 "$ROOT/scripts/harness.py" context "$ROOT" '~/.psai')"   # same HOME: the nudge counts unmanaged skills
python3 -c "
import json, sys; d = json.loads(sys.argv[1])['hookSpecificOutput']
sys.exit(0 if d['hookEventName'] == 'SessionStart' and d['additionalContext'] == sys.argv[2] + '\n' else 1)" "$out" "$ctx"
res "claude hook: SessionStart additionalContext is the live nudge" $?
for ev in SessionStart:PSAI_ROLE SubagentStart:subagent; do
  e="${ev%%:*}"
  if [ "${ev#*:}" = PSAI_ROLE ]; then o="$(env -u PSAI_HOME PSAI_ROLE=doer HOME="$T/claude" bash "$ROOT/plugins/claude/hooks/session-start.sh" "$e")"
  else o="$(env -u PSAI_HOME -u PSAI_ROLE HOME="$T/claude" bash "$ROOT/plugins/claude/hooks/session-start.sh" "$e")"; fi
  python3 -c "
import json, sys; d = json.loads(sys.argv[1])['hookSpecificOutput']; c = d['additionalContext']
sys.exit(0 if d['hookEventName'] == sys.argv[2] and sys.argv[3] in c and sys.argv[4] not in c else 1)" "$o" "$e" "$ROLEWANT" "$WANT"
  res "claude hook: $e with ${ev#*:} gets the role-mode nudge (no routing)" $?
done

capture_ts() { # file: a pi/omp extension that records the system prompt at before_agent_start
  printf '%s\n' 'import { writeFileSync } from "node:fs";' \
    'export default function (pi: any) { pi.on("before_agent_start", async (e: any) => {' \
    "  writeFileSync(process.env.PSAI_CAPTURE as string, Array.isArray(e.systemPrompt) ? e.systemPrompt.join($NL) : e.systemPrompt); }); }" > "$1"
}

if command -v pi >/dev/null; then
  h="$T/pi"; mkdir -p "$h/w" "$h/.pi/agent/extensions"; ln -s "$ROOT" "$h/.psai"
  ln -s "$h/.psai/plugins/pi/psai.ts" "$h/.pi/agent/extensions/psai.ts"
  capture_ts "$h/.pi/agent/extensions/zz-capture.ts"
  echo '{"providers":{"fake":{"baseUrl":"http://127.0.0.1:9/v1","api":"openai-completions","apiKey":"none","models":[{"id":"m"}]}}}' > "$h/.pi/agent/models.json"
  (cd "$h/w" && env -u PSAI_HOME -u PSAI_ROLE HOME="$h" PSAI_CAPTURE="$h/cap" timeout 60 pi -p --no-session --model fake/m hi </dev/null >/dev/null 2>&1)
  grep -Fq "$WANT" "$h/cap" 2>/dev/null; res "pi extension: nudge in the system prompt" $?
  (cd "$h/w" && env -u PSAI_HOME PSAI_ROLE=doer HOME="$h" PSAI_CAPTURE="$h/cap-role" timeout 60 pi -p --no-session --model fake/m hi </dev/null >/dev/null 2>&1)
  role_ok "$h/cap-role"; res "pi extension: PSAI_ROLE session gets the role-mode nudge" $?
else skip "pi not installed"; fi

if command -v omp >/dev/null; then
  h="$T/omp"; mkdir -p "$h/w" "$h/.omp/agent/extensions"; ln -s "$ROOT" "$h/.psai"
  ln -s "$h/.psai/plugins/omp/psai.ts" "$h/.omp/agent/extensions/psai.ts"
  capture_ts "$h/.omp/agent/extensions/zz-capture.ts"
  for v in "" doer; do
    (cd "$h/w" && env -u PSAI_HOME $([ -z "$v" ] && echo "-u PSAI_ROLE") ${v:+PSAI_ROLE=$v} HOME="$h" PSAI_CAPTURE="$h/cap$v" \
      ANTHROPIC_API_KEY=dummy ANTHROPIC_BASE_URL=http://127.0.0.1:9 timeout 25 omp -p --no-session --no-title hi </dev/null >/dev/null 2>&1)
  done
  grep -Fq "$WANT" "$h/cap" 2>/dev/null; res "omp extension: nudge in the system prompt" $?
  role_ok "$h/capdoer"; res "omp extension: PSAI_ROLE session gets the role-mode nudge" $?
else skip "omp not installed"; fi

if command -v opencode >/dev/null; then
  h="$T/oc"; mkdir -p "$h/w" "$h/.config/opencode/plugin"; ln -s "$ROOT" "$h/.psai"
  printf '// psai: managed by install.sh\nexport { Psai } from "%s/.psai/plugins/opencode/psai.js";\n' "$h" > "$h/.config/opencode/plugin/psai.js"
  printf '%s\n' 'import { writeFileSync } from "node:fs";' \
    "export const Zz = async () => ({ \"experimental.chat.system.transform\": async (_i, o) => { writeFileSync(process.env.PSAI_CAPTURE, o.system.join($NL)); } });" \
    > "$h/.config/opencode/plugin/zz-capture.js"
  for v in "" doer; do
    (cd "$h/w" && env -u PSAI_HOME $([ -z "$v" ] && echo "-u PSAI_ROLE") ${v:+PSAI_ROLE=$v} HOME="$h" XDG_CONFIG_HOME="$h/.config" XDG_DATA_HOME="$h/.d" XDG_CACHE_HOME="$h/.c" XDG_STATE_HOME="$h/.s" \
      PSAI_CAPTURE="$h/cap$v" ANTHROPIC_API_KEY=dummy OPENCODE_CONFIG_CONTENT='{"provider":{"anthropic":{"options":{"baseURL":"http://127.0.0.1:9/v1"}}}}' \
      timeout 30 opencode run --model anthropic/claude-haiku-4-5 hi </dev/null >/dev/null 2>&1)
  done
  grep -Fq "$WANT" "$h/cap" 2>/dev/null; res "opencode plugin: nudge in the system prompt" $?
  role_ok "$h/capdoer"; res "opencode plugin: PSAI_ROLE session gets the role-mode nudge" $?
else skip "opencode not installed"; fi

# Subagent detection, called directly with stand-ins for the host (no tool binary needed): an omp task child
# (ctx.agent.kind "sub") and an opencode child session (it has a parentID) get the role-mode text.
if command -v node >/dev/null; then
  h="$T/sub"; mkdir -p "$h"; ln -s "$ROOT" "$h/.psai"
  cat > "$h/t.mjs" <<'JS'
const [, , root, want, rolewant] = process.argv;
const ok = (s, sub) => sub ? s.includes(rolewant) && !s.includes(want) : s.includes(want);
let h; await (await import(root + "/plugins/omp/psai.ts")).default({ on: (_e, f) => (h = f) });
const omp = async (kind) => ((await h({ systemPrompt: [] }, { agent: { kind } })).systemPrompt || []).join("\n");
const { Psai } = await import(root + "/plugins/opencode/psai.js");
const hooks = await Psai({ client: { session: { get: async ({ path }) => ({ data: { parentID: path.id === "child" ? "p" : undefined } }) } } });
const oc = async (id) => { const o = { system: [] }; await hooks["experimental.chat.system.transform"]({ sessionID: id }, o); return o.system.join("\n"); };
const r = [ok(await omp("main"), false), ok(await omp("sub"), true), ok(await oc("top"), false), ok(await oc("child"), true)];
console.log(r.map((x) => (x ? 0 : 1)).join(" "));
JS
  read -r a b c d < <(cd "$h" && env -u PSAI_HOME -u PSAI_ROLE HOME="$h" node "$h/t.mjs" "$ROOT" "$WANT" "$ROLEWANT" 2>/dev/null || echo 1 1 1 1)
  res "omp extension: a main session gets the routing nudge" "$a"
  res "omp extension: a task subagent gets the role-mode nudge" "$b"
  res "opencode plugin: a top-level session gets the routing nudge" "$c"
  res "opencode plugin: a child (task) session gets the role-mode nudge" "$d"
else skip "node not installed (subagent detection)"; fi

exit $((fails > 0))
