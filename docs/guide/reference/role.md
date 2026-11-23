# A role

A role file is the brief a fresh role agent follows. Put it in `roles/<name>.md` inside the workflow that uses it, or in `<stack>-shared/roles/` when several workflows share it. The role's name is the file's name.

```md
---
may_change: tests
read: [acme-shared:guides/testing.md]
skills: { required: [acme-lint], optional: [] }
model: strong
---
# Role: tester

You add tests from the task (not from the implementation) and run them. Return `done` or `tests fail` with the failures.
```

| Key | Meaning |
|---|---|
| `may_change` | `anything`, `tests` or `nothing`. After the role returns, `work/check-diff.sh` compares the diff with it; a violation is reverted and the role re-run once, then escalated. `tests` allows test paths (`tests/`, `*_test.go`, `test_*.py`, ...; `TESTS_ALLOW` adds a regex). |
| `read` | refs the role reads first |
| `skills` | `required` skills must be installed, or `work` escalates before starting the role; `optional` ones are listed in its brief |
| `model` | a tier (`fast`, `balanced`, `strong`) or ids per tool (`{claude: opus, pi: anthropic/claude-opus-5-5}`). Claude Code maps tiers to `haiku`, `sonnet`, `opus`; pi gets `--model` with its id; opencode and omp can't set a model per call, so the run uses the current one and the report says so. |

**Knowledge:** when your stack has `knowledge/roles/<name>/INDEX.md`, `work` gives it to the role. See [knowledge.md](knowledge.md).

**Role agents:** every role starts with a fresh context: Claude Code's Agent tool, opencode's and omp's `task` tool, or a `pi -p` process. Its prompt says it is a role inside a running workflow, so it never routes or starts workflows.
