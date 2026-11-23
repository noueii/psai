# Skills a stack ships or needs

**A stack's own skill:** `skills/<stack>-<name>/SKILL.md` plus its files, in the [Agent Skills](https://agentskills.io/specification) format. The frontmatter has only the standard fields, and a quoted description that says what the skill does and "Use when ...":

```md
---
name: acme-changelog
description: "Adds one line per change to CHANGELOG.md. Use when you change files in a repo."
---
After a change, append `- <what changed and why>` to CHANGELOG.md.
```

**A skill a role or step needs:** name it in `skills: {required: [...], optional: [...]}`. If someone else publishes it, the consumer installs it through their tool's channel; say so in your README. When a required skill is missing, `work` escalates before starting the role and offers `customize-harness`.

**A skill for one repo only** belongs in that repo (`.claude/skills/`, `.agents/skills/`), not in a stack.
