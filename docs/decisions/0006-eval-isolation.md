# 0006: Evals load the harness per run, never via the real HOME (2026-11-21)
- Decision: each eval run copies the harness and the fixture to a temp directory and sets `HARNESS_HOME`. The engine reads `HARNESS_HOME` in place of `~/.harness`.
  - **Claude Code:** `--plugin-dir plugins/claude` (the same SessionStart nudge a real install uses) plus a throwaway skills plugin, `--setting-sources project`, `--no-session-persistence`, `--strict-mcp-config`.
  - **omp:** RPC mode with `--extension plugins/omp/psai.ts` and a `--config` overlay (`skills.customDirectories`, user skill folders off).
  - The harness copy leaves out the upstream scenarios and graders, so the agent never sees the expected answers.
  - **pi and opencode:** skipped when they have no working provider. No credentials are ever copied.
- Why: the owner forbade installing into the real HOME and copying credentials. Claude's `--bare` needs an API key, which isn't available here, so the OAuth login is used in place.
- Source: the owner's v2 spec; probes on 2026-11-21 (pi: no key for openai-codex and no minimax balance; opencode: provider unreachable).
