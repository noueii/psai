# Your knowledge and the stage

Your own stack is the one writable place psai uses. Its clone is `$PSAI_STACK`, or `~/psai-stack` when that isn't set (the `work` skill's `your-stack.md`).

## Knowledge
| File | What |
|---|---|
| `knowledge/inbox.md` | findings during tasks (capture-knowledge), as dated entries; uncommitted until the retro |
| `knowledge/roles/<role>/inbox.md` | findings for one role |
| `knowledge/facts/<topic>.md` | promoted facts, prose with sources |
| `knowledge/decisions/YYYY-MM-DD-<slug>.md` | promoted decisions: Decision / Why / Source |
| `knowledge/INDEX.md`, `knowledge/roles/<role>/INDEX.md` | one line per file; `work` gives a role its index |

An inbox entry:
```md
## 2026-11-23: Tests run with python3 -m unittest
- Tag: fact | decision | proposed-rule
- Source: the owner in chat
- What: the repo's tests run with `python3 -m unittest -q`.
- Why: not stated
```

## The stage
Everything except inbox entries is changed in **the stage**: a git worktree of your stack at `<git dir>/psai-stage`, on the branch `psai/stage`. Your tools may read the clone live, so it is never edited directly. At the end of a task, the retro (or a `sync` node):
1. commits the stage;
2. renames the branch to `psai/<date>-<slug>`;
3. pushes it and opens one PR with `gh`. With no remote, it leaves the branch.

You merge the PR, then update the stack in your tools.
