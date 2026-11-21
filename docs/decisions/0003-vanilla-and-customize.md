# 0003: Ship vanilla; customize-harness builds each user's setup (2026-11-21)
- Decision: psai ships only the machinery (`work`, `customize-harness`, `capture-knowledge`, global.md, LAYOUT.md, scripts, installer, evals) and empty folders with READMEs. Workflows, steps, roles, guides and templates are built WITH the user. Design patterns are offered as options, never pre-built. The only built-in rule: no matching workflow, or unsure: escalate.
- Why: a harness that encodes one person's process can't be adopted by anyone else or changed safely. Test content stays neutral for the same reason.
- Source: v2 design review.
