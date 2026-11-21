# plugins/

One plugin per tool. Each injects the same always-on text, `python3 scripts/harness.py context`, into every session, read live from the harness (`$PSAI_HOME` or `~/.psai`). Routing therefore never depends on a skill description. This is the only injection path; `install.sh` sets up the plugin for each tool that is present:
- [claude/](claude/README.md): a Claude Code plugin with a SessionStart hook (`hookSpecificOutput.additionalContext`), installed through this repo's `.claude-plugin/marketplace.json`.
- [pi/](pi/README.md): a pi extension; `before_agent_start` appends to the system prompt.
- [omp/](omp/README.md): an omp extension; `before_agent_start` appends to the system prompt.
- [opencode/](opencode/README.md): an opencode plugin; `experimental.chat.system.transform` adds to the system prompt.
