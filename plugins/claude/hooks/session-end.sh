#!/usr/bin/env bash
# SessionEnd hook: close this session's ledger record (scripts/ledger.py end). It counts what the session captured,
# notes drift, and marks the record retro-pending when it ran a workflow or captured something without a retro: the
# next session's nudge then asks for the retro (the safety net). Reads the hook input (session_id) from stdin.
H="${PSAI_HOME:-$HOME/.psai}"
[ -f "$H/scripts/ledger.py" ] || exit 0
[ -n "${PSAI_ROLE:-}" ] && exit 0
# the hook input arrives on stdin; never wait long for it when there is none (the heredoc below is python's stdin)
[ -t 0 ] || export PSAI_HOOK_INPUT="$(timeout 1 cat 2>/dev/null)"
python3 - "$H" <<'PY'
import json, os, subprocess, sys
h = sys.argv[1]
data = {}
try:
    data = json.loads(os.environ.get("PSAI_HOOK_INPUT") or "{}")
except Exception:
    data = {}
args = ["end"] + (["--id", data["session_id"]] if data.get("session_id") else [])
subprocess.run([sys.executable, os.path.join(h, "scripts", "ledger.py"), *args], capture_output=True)
PY
exit 0
