# hooks/

The Claude Code plugin's hooks, loaded from [hooks.json](hooks.json) when psai is installed as a plugin. One SessionStart hook prints the routing nudge, `skills/request-router/nudge.md`, which Claude Code adds to the session's context. Keep it to that one command: the nudge text lives in the skill.
