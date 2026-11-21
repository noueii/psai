# plugins/claude/hooks/

`hooks.json` registers the hooks. `session-start.sh` prints the live context as additionalContext and opens the session's ledger record; `session-end.sh` closes it (`scripts/ledger.py`).
