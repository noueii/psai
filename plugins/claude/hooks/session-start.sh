#!/usr/bin/env bash
# SessionStart hook: print the live psai context as hookSpecificOutput.additionalContext.
# Reads the harness at $HARNESS_HOME or ~/.harness, so the text is never a stale copy.
H="${HARNESS_HOME:-$HOME/.harness}"
[ -f "$H/scripts/harness.py" ] || exit 0
python3 - "$H" <<'PY'
import json, os, subprocess, sys
h = sys.argv[1]
shown = h if os.environ.get("HARNESS_HOME") else "~/.harness"
ctx = subprocess.run([sys.executable, os.path.join(h, "scripts", "harness.py"), "context", h, shown],
                     capture_output=True, text=True).stdout
if ctx:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))
PY
