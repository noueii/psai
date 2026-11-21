---
name: capture-knowledge
description: "Records a fact, a decision or a proposed rule as a dated, sourced entry in a knowledge inbox; the retro promotes them by PR. Use when you learn something true about a repo or tool, when you decide something without escalating, when the owner states or corrects a preference, or when you think a rule should change future work."
---

# capture-knowledge

Knowledge is descriptive (what's true, what was decided and why). Rules are prescriptive and live in guides, roles and steps, which change only through `customize-harness`.

## Where
`psai` prints the inbox to append to (run it as the nudge says if it isn't on PATH):
- a finding for one role: `psai resolve --write knowledge roles/<role>/inbox.md` (from a workflow of another stack, `<stack>:roles/<role>/inbox.md`);
- everything else: `psai resolve --write knowledge inbox.md`.

First check the knowledge index (`psai resolve --all knowledge INDEX.md`); if the finding is already recorded, don't add it again. Skip:
- what the repo itself records (code, git history, its own docs);
- secrets;
- company content (that belongs in the company's repos).

## Entry
Append to the end of the inbox, creating it (and its folder's `INDEX.md`) with a one-line title if it doesn't exist yet:

```md
## YYYY-MM-DD: <short title>
- Tag: fact | decision | proposed-rule
- Source: <who or what: the owner in chat, PR #12 review, a repo path, the task>
- What: <one or two lines>
- Why: <the reason given, or "not stated">
```

Use `proposed-rule` for anything you think should change future work. It stays a proposal until the owner accepts it.

## Promote (at the retro, by PR only)
Inbox entries stay as local, uncommitted edits; nothing goes to GitHub while a task runs. The retro skill, at the end of the task, promotes stable entries in the stage worktree (`psai sync stage`), never in the live setup:
- a fact goes to `knowledge/facts/<topic>.md`;
- a decision goes to `knowledge/decisions/YYYY-MM-DD-<slug>.md`;
- an accepted proposed rule goes into a guide, role or step, using `customize-harness`.

It updates `knowledge/INDEX.md` there and deletes the promoted entries from the live inbox; the retro's one PR (or sync's) carries it all. The owner merges it.
