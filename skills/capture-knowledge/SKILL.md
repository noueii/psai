---
name: capture-knowledge
description: "Records a fact, a decision or a proposed rule as a dated, sourced entry in a knowledge inbox in your stack; the retro promotes them by PR. Use when you learn something true about a repo or tool, when you decide something without escalating, when the owner states or corrects a preference, or when you think a rule should change future work."
---

# capture-knowledge

Knowledge is descriptive (what's true, what was decided and why). Rules are prescriptive and live in guides, roles, steps and `*-rules` skills, which change only through `customize-harness`.

## Where
Knowledge lives in your stack `S` (the `work` skill's `your-stack.md`); no stack yet: put the entry in the final report and offer to create one.
- a finding for one role: `S/knowledge/roles/<role>/inbox.md`;
- everything else: `S/knowledge/inbox.md`.

First read `S/knowledge/INDEX.md` (and the role's `INDEX.md`); if the finding is already recorded, don't add it again. Skip:
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
Inbox entries stay as uncommitted edits in `S`; nothing goes to GitHub while a task runs. The retro promotes stable entries in the stage (`your-stack.md`), never in `S` itself:
- a fact goes to `knowledge/facts/<topic>.md`;
- a decision goes to `knowledge/decisions/YYYY-MM-DD-<slug>.md`;
- an accepted proposed rule goes into a guide, role, step or rules skill, using `customize-harness`.

It updates `knowledge/INDEX.md` in the stage and deletes the promoted entries from the inbox in `S`. The retro's PR carries it all; the owner merges it.
