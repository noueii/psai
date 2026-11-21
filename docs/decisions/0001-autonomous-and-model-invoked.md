# 0001: Model-invoked skills only (2026-11-21)
- Decision: every skill is model-invoked: no `disable-model-invocation`, no slash commands. Agents start the machinery on their own and ask a human only through the fixed escalation block.
- Why: the harness runs workflows without a human triggering each step, and check.sh can verify this.
- Source: psai v1 design.
