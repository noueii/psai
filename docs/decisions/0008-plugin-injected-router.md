# 0008: A plugin injects a live nudge; request-router routes (2026-11-21)
- Decision: routing never depends on a skill description. Every tool gets one plugin that injects `scripts/harness.py context`, read live: global.md, owner.md, "run the request-router skill first", and each workflow's name and `when` (108 words in vanilla, about 8 more per workflow). The `request-router` skill holds the logic:
  - a matching workflow runs;
  - a repeatable task with no workflow escalates and offers `customize-harness`;
  - a one-off is handled normally.

  `work` is the engine, read once a workflow is chosen.
- Per tool, verified against the installed versions:
  - **Claude Code 2.1:** a plugin with a SessionStart hook (`startup|resume|clear|compact`) returning `hookSpecificOutput.additionalContext`. It's installed from this repo's marketplace; a directory marketplace reads the plugin live from the clone.
  - **pi 0.80:** an extension in `~/.pi/agent/extensions/` (links are followed); `before_agent_start` returns `systemPrompt`.
  - **omp 18.11:** the same, with `systemPrompt` as a string array.
  - **opencode 1.18:** a plugin in `~/.config/opencode/plugin/` (singular; `plugins/` and symlinked files aren't loaded), so install.sh writes a stub that imports the live plugin. It uses `experimental.chat.system.transform`.

  v1's import lines and marked blocks are removed on upgrade.
- Why: a skill description triggers unreliably, and pasted copies go stale. One live injection path per tool keeps every session current.
- Source: the owner's v2 review; `scripts/test-plugins.sh`.
