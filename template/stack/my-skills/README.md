# my-skills/

This stack's own skills, and the format of `skills.yaml` (other people's skills this stack pins). psai links each into the tools' skill folders when the stack is installed; a role always gets its own stack's copy.

Format: flat `my-skills/<name>/SKILL.md`, where `name` equals the folder name, plus any supporting files next to it. The `description` is quoted, says what the skill does and "Use when ...". Prefix the name with the stack's (`acme-changelog`): the tools' folders are flat, and psai's own names (`work`, `request-router`, ...) are reserved. Example:
```md
---
name: acme-change-notes
description: "Appends a one-line entry to CHANGES.md for each change. Use when you change files in a repo."
---
# acme-change-notes
Append `- <date>: <what changed>` to CHANGES.md at the repo root; create the file if it's missing.
```

## skills.yaml
At the stack's root. Every entry is pinned to a tag or a commit, never a branch; psai fetches each into `~/.psai/state/skills-cache/<stack>/<name>/`.
```yaml
skills:
  - name: pdf                          # the folder name the tools see
    source: github:anthropics/skills   # github:owner/repo, or any git URL
    path: skills/pdf                   # the folder holding SKILL.md, inside the repo
    ref: v1.2.0                        # a tag or a commit
ignore: []                             # skills other tools manage: never reported or adopted
```
