# my-skills/

Your own reusable skills, and the format of `skills.yaml` (other people's skills). psai ships this folder empty. `install.sh` links each skill here into `~/.claude/skills` and `~/.agents/skills`, like psai's own, so every tool sees it. `customize-harness` writes new ones here with you.

Format: flat `my-skills/<name>/SKILL.md`, where `name` equals the folder name, plus any supporting files next to it. The `description` is quoted, says what the skill does and "Use when ...". Don't reuse a name from psai's `skills/`; prefix yours if a name is common (`my-review`). Example:
```md
---
name: change-notes
description: "Appends a one-line entry to CHANGES.md for each change. Use when you change files in a repo."
---
# change-notes
Append `- <date>: <what changed>` to CHANGES.md at the repo root; create the file if it's missing.
```

## Where a skill goes
- Your own, reusable: here.
- Someone else's: a pinned entry in `skills.yaml` at the root of your fork.
- One repo only: that repo's `.agents/skills/<name>/`, with a link from `.claude/skills/<name>` so Claude Code sees it too. List it as optional on roles, since other repos don't have it.

Roles and steps name the skills they need: `skills: {required: [...], optional: [...]}` (roles/README.md).

## skills.yaml
Yours; psai doesn't ship one. Every entry is pinned to a tag or a commit, never a branch. `install.sh` fetches each into the git-ignored `.skills-cache/<name>/` and links it; re-running fetches only when a pin changes.
```yaml
skills:
  - name: pdf                          # the folder name the tools see
    source: github:anthropics/skills   # github:owner/repo, or any git URL
    path: skills/pdf                   # the folder holding SKILL.md, inside the repo
    ref: v1.2.0                        # a tag or a commit
ignore: [orca-cli, orchestration]      # skills other tools manage: never reported or adopted
```

## Unmanaged skills
`python3 ~/.psai/scripts/harness.py skills` lists every skill your tools can see, where it lives, and which tools see it. A skill in a tool folder that psai doesn't link and that isn't ignored is unmanaged: reported (by `scripts/check.sh` and the injected nudge), never blocked. `./install.sh --adopt <name>` (or `customize-harness`) brings one in: your own moves here and is linked back; one installed from a repo (as `npx skills` records in `~/.agents/.skill-lock.json`) becomes a pinned `skills.yaml` entry, and its old copy is kept in `.skills-cache/.adopted/`.
