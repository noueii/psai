# 0003: Ship vanilla; customize-harness builds the owner's setup (2026-11-21)
- Decision: psai ships only the machinery (`work`, `customize-harness`, `capture-knowledge`, global.md, LAYOUT.md, scripts, installer, evals) and empty folders with READMEs. Workflows, steps, roles, guides and templates are built WITH the user. Design patterns are offered as options, never pre-built. The only built-in rule is "no matching workflow, or unsure: escalate".
- Why: the owner's change to the v2 spec. A harness that encodes one person's process can't be adopted by anyone else, or changed safely.
- Source: the coordinator's message "v2 ships vanilla", 2026-11-21.
