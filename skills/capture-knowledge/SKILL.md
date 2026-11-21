---
name: capture-knowledge
description: "Records a preference, rule or decision as a dated inbox entry in ~/.harness/knowledge, and promotes inbox entries into topic files through a PR. Use when the owner states or corrects a preference, when you make a decision without escalating, when a reviewer or human comment reveals a rule, or when an inbox has grown enough to promote."
---

# Capture knowledge

Knowledge lives in `~/.harness/knowledge/`, plain Markdown:
- shared: `preferences/`, `decisions/`, `inbox.md`;
- per role: `roles/<engineer|qa|reviewer>/INDEX.md` and `inbox.md`.

## When
- The owner states, repeats or corrects a preference.
- You decide something instead of escalating (also log it in the PR description).
- A review comment or failure reveals a rule worth keeping.

Skip one-off facts, anything the repo already records (code, git history, its own docs), secrets, and company-specific content: that belongs in the company repo's docs.

## Where
Role-specific lessons go to that role's `inbox.md`; everything else to `knowledge/inbox.md`. Check `INDEX.md` and the topic files first; if it's already there, don't add it again.

## Entry format
Append to the end of the inbox:

```md
## YYYY-MM-DD: <short title>
- Source: <who or what: owner in chat, PR #12 review, repo path, task name>
- What: <the preference or decision, one or two lines>
- Why: <the reason given, or "not stated">
```

## Promote
Inbox entries stay as uncommitted local edits in `~/.harness`; only topic files go through git. When entries are clearly stable (repeated, or confirmed by the owner), promote them by PR, never by switching branches in `~/.harness` (live sessions read it):
1. `git -C ~/.harness fetch && git -C ~/.harness worktree add "$(mktemp -d)/k" -b knowledge/<date>-<slug> origin/main`, then work in that worktree.
2. Write each entry into the right topic file (`preferences/<topic>.md`, `decisions/<date>-<slug>.md`, or the role's folder) and update the matching `INDEX.md`. Don't touch the inbox files there.
3. Commit, push and open a PR against main titled `knowledge: <summary>`. The owner merges it; never merge it yourself.
4. Delete the promoted entries from the inbox in `~/.harness`, then remove the worktree.
