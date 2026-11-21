#!/usr/bin/env bash
# SessionStart / SubagentStart hook: print the live psai context as hookSpecificOutput.additionalContext.
# Usage: session-start.sh [SessionStart|SubagentStart]. A subagent (and any session with $PSAI_ROLE) gets the
# role-mode text, which says not to route. It runs `psai context` live, so the text is never a stale copy.
# A top-level SessionStart also opens (or resumes) this session's ledger record (scripts/ledger.py), from the hook
# input on stdin: session_id, cwd, transcript_path.
H="${PSAI_HOME:-$HOME/.psai}"   # psai-bootstrap: the home; everything else goes through the psai command
P="$H/framework/scripts/psai.py"; [ -f "$P" ] || P="$H/scripts/psai.py"; [ -f "$P" ] || P="$(command -v psai)" || exit 0   # psai-bootstrap
# the hook input arrives on stdin; never wait long for it when there is none (the heredoc below is python's stdin)
[ -t 0 ] || export PSAI_HOOK_INPUT="$(timeout 1 cat 2>/dev/null)"
python3 - "$H" "${1:-SessionStart}" "$P" <<'PY'
import json, os, subprocess, sys
h, event, psai = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
try:  # the hook input (session_id, cwd, transcript_path), read by bash below
    data = json.loads(os.environ.get("PSAI_HOOK_INPUT") or "{}")
except Exception:
    data = {}
if event == "SessionStart" and not os.environ.get("PSAI_ROLE"):
    sid = data.get("session_id") or f"claude-{os.getppid()}"
    args = ["start", "--tool", "claude", "--id", sid, "--project", data.get("cwd") or os.getcwd()]
    if data.get("transcript_path"):
        args += ["--transcript", data["transcript_path"]]
    subprocess.run([sys.executable, psai, "ledger", *args], capture_output=True)
shown = h if os.environ.get("PSAI_HOME") else "~/.psai"
mode = "role-context" if event == "SubagentStart" else "context"
ctx = subprocess.run([sys.executable, psai, mode, h, shown],
                     capture_output=True, text=True).stdout
if ctx:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}))
PY
