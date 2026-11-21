#!/usr/bin/env bash
# SessionStart / SubagentStart hook: print the live psai context as hookSpecificOutput.additionalContext.
# Usage: session-start.sh [SessionStart|SubagentStart]. A subagent (and any session with $PSAI_ROLE) gets the
# role-mode text, which says not to route. Reads $PSAI_HOME or ~/.psai, so the text is never a stale copy.
H="${PSAI_HOME:-$HOME/.psai}"
[ -f "$H/scripts/harness.py" ] || exit 0
python3 - "$H" "${1:-SessionStart}" <<'PY'
import json, os, subprocess, sys
h, event = sys.argv[1], sys.argv[2]
shown = h if os.environ.get("PSAI_HOME") else "~/.psai"
mode = "role-context" if event == "SubagentStart" else "context"
ctx = subprocess.run([sys.executable, os.path.join(h, "scripts", "harness.py"), mode, h, shown],
                     capture_output=True, text=True).stdout
if ctx:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}))
PY
