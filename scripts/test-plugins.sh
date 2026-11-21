#!/usr/bin/env bash
# Prove, without AI and without network, that each tool's psai plugin puts the live nudge into the session.
# Each tool runs in a temp HOME with our plugin plus a test-only capture plugin that records the final system
# prompt; the model call then fails against a closed local port. Claude Code's hook is run directly.
# Usage: scripts/test-plugins.sh   (prints "ok"/"FAIL"/"skip" lines; exits 1 on any failure)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
fails=0
res() { if [ "$2" = 0 ]; then echo "  ok   $1"; else echo "  FAIL $1"; fails=$((fails + 1)); fi; }
skip() { echo "  skip $1"; }
WANT='run the request-router skill first'
NL='String.fromCharCode(10)'

# Claude Code: run the SessionStart hook as the plugin would.
mkdir -p "$T/claude"; ln -s "$ROOT" "$T/claude/.harness"
out="$(env -u HARNESS_HOME HOME="$T/claude" bash "$ROOT/plugins/claude/hooks/session-start.sh")"
ctx="$(python3 "$ROOT/scripts/harness.py" context "$ROOT" '~/.harness')"
python3 -c "
import json, sys; d = json.loads(sys.argv[1])['hookSpecificOutput']
sys.exit(0 if d['hookEventName'] == 'SessionStart' and d['additionalContext'] == sys.argv[2] + '\n' else 1)" "$out" "$ctx"
res "claude hook: SessionStart additionalContext is the live nudge" $?

capture_ts() { # file: a pi/omp extension that records the system prompt at before_agent_start
  printf '%s\n' 'import { writeFileSync } from "node:fs";' \
    'export default function (pi: any) { pi.on("before_agent_start", async (e: any) => {' \
    "  writeFileSync(process.env.PSAI_CAPTURE as string, Array.isArray(e.systemPrompt) ? e.systemPrompt.join($NL) : e.systemPrompt); }); }" > "$1"
}

if command -v pi >/dev/null; then
  h="$T/pi"; mkdir -p "$h/w" "$h/.pi/agent/extensions"; ln -s "$ROOT" "$h/.harness"
  ln -s "$h/.harness/plugins/pi/psai.ts" "$h/.pi/agent/extensions/psai.ts"
  capture_ts "$h/.pi/agent/extensions/zz-capture.ts"
  echo '{"providers":{"fake":{"baseUrl":"http://127.0.0.1:9/v1","api":"openai-completions","apiKey":"none","models":[{"id":"m"}]}}}' > "$h/.pi/agent/models.json"
  (cd "$h/w" && env -u HARNESS_HOME HOME="$h" PSAI_CAPTURE="$h/cap" timeout 60 pi -p --no-session --model fake/m hi >/dev/null 2>&1)
  grep -Fq "$WANT" "$h/cap" 2>/dev/null; res "pi extension: nudge in the system prompt" $?
else skip "pi not installed"; fi

if command -v omp >/dev/null; then
  h="$T/omp"; mkdir -p "$h/w" "$h/.omp/agent/extensions"; ln -s "$ROOT" "$h/.harness"
  ln -s "$h/.harness/plugins/omp/psai.ts" "$h/.omp/agent/extensions/psai.ts"
  capture_ts "$h/.omp/agent/extensions/zz-capture.ts"
  (cd "$h/w" && env -u HARNESS_HOME HOME="$h" PSAI_CAPTURE="$h/cap" ANTHROPIC_API_KEY=dummy ANTHROPIC_BASE_URL=http://127.0.0.1:9 \
    timeout 25 omp -p --no-session --no-title hi >/dev/null 2>&1)
  grep -Fq "$WANT" "$h/cap" 2>/dev/null; res "omp extension: nudge in the system prompt" $?
else skip "omp not installed"; fi

if command -v opencode >/dev/null; then
  h="$T/oc"; mkdir -p "$h/w" "$h/.config/opencode/plugin"; ln -s "$ROOT" "$h/.harness"
  printf '// psai: managed by install.sh\nexport { Psai } from "%s/.harness/plugins/opencode/psai.js";\n' "$h" > "$h/.config/opencode/plugin/psai.js"
  printf '%s\n' 'import { writeFileSync } from "node:fs";' \
    "export const Zz = async () => ({ \"experimental.chat.system.transform\": async (_i, o) => { writeFileSync(process.env.PSAI_CAPTURE, o.system.join($NL)); } });" \
    > "$h/.config/opencode/plugin/zz-capture.js"
  (cd "$h/w" && env -u HARNESS_HOME HOME="$h" XDG_CONFIG_HOME="$h/.config" XDG_DATA_HOME="$h/.d" XDG_CACHE_HOME="$h/.c" XDG_STATE_HOME="$h/.s" \
    PSAI_CAPTURE="$h/cap" ANTHROPIC_API_KEY=dummy OPENCODE_CONFIG_CONTENT='{"provider":{"anthropic":{"options":{"baseURL":"http://127.0.0.1:9/v1"}}}}' \
    timeout 30 opencode run --model anthropic/claude-haiku-4-5 hi >/dev/null 2>&1)
  grep -Fq "$WANT" "$h/cap" 2>/dev/null; res "opencode plugin: nudge in the system prompt" $?
else skip "opencode not installed"; fi

exit $((fails > 0))
