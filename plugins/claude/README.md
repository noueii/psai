# plugins/claude/

The Claude Code plugin: `.claude-plugin/plugin.json` and a SessionStart hook (matcher `startup|resume|clear|compact`) that runs `hooks/session-start.sh`. The hook prints `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": <context>}}`. install.sh adds the repo as a marketplace (`claude plugin marketplace add <clone>`) and installs `psai@psai`.
