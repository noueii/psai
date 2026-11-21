---
name: capture-knowledge
description: "Records a fact, a decision or a proposed rule as a dated, sourced entry in a knowledge inbox, and promotes inbox entries by PR. Use when you learn something true about a repo or tool, when you decide something without escalating, when the owner states or corrects a preference, or when you think a rule should change future work."
---

# capture-knowledge

`H` is the harness root (`$HARNESS_HOME` or `~/.harness`). Knowledge is descriptive (what's true, what was decided and why). Rules are prescriptive and live in guides, roles and steps, which change only through `customize-harness`.

## Where
- A finding for one role goes to `H/knowledge/roles/<role>/inbox.md`.
- Everything else goes to `H/knowledge/inbox.md`.

First check `H/knowledge/INDEX.md`; if the finding is already recorded, don't add it again. Skip:
- what the repo itself records (code, git history, its own docs);
- secrets;
- company content (that belongs in the company's repos).

## Entry
Append to the end of the inbox:

```md
## YYYY-MM-DD: <short title>
- Tag: fact | decision | proposed-rule
- Source: <who or what: the owner in chat, PR #12 review, a repo path, the task>
- What: <one or two lines>
- Why: <the reason given, or "not stated">
```

Use `proposed-rule` for anything you think should change future work. It stays a proposal until the owner accepts it.

## Promote (by PR only)
Inbox entries stay as local, uncommitted edits. Promote stable ones in a separate worktree off `origin/main`; never switch branches in the live `H`:
- a fact goes to `knowledge/facts/<topic>.md`;
- a decision goes to `knowledge/decisions/YYYY-MM-DD-<slug>.md`;
- an accepted proposed rule goes into a guide, role or step, using `customize-harness`.

Update `knowledge/INDEX.md`, commit, push, and open a PR titled `knowledge: <summary>`. The owner merges it. Afterwards, delete the promoted entries from the local inbox.
