---
name: request-router
description: "Decides how to handle a request: runs one of the owner's workflows (the skills named workflow-*), offers to set one up, or handles it directly. Use when any request arrives, before acting on it, except a quick question or a one-off reply."
---

# request-router

1. **Load the rules.** Load every skill named `<stack>-rules` that you can see (Claude Code shows plugin skills as `<plugin>:<name>`). They hold the always-on rules of each installed stack. Your own stack's rules (the `work` skill's `your-stack.md`) win over another stack's.
2. **List the workflows:** every skill whose name starts with `workflow-`. Its description says what it's for. There may be none yet.
3. **Decide:**
   - **Match** (a workflow whose description fits, even if the request doesn't name it): load that workflow skill, then the `work` skill, and run it from its `start`. Don't do any of the work before that.
   - **No match, but repeatable**: escalate with the fixed block (the `work` skill's `escalation.md`), kind `escalation`, node `route`, offering to set up a workflow with `customize-harness`.
   - **No match, one-off**: handle it normally, with no workflow and no escalation.

   Judge the **kind** of work, not this one request. Changing code or docs (a feature, a fix, a helper, a refactor), reviews, reports and recurring chores are repeatable kinds, even the first time one is asked. One-off means a question, an explanation, or a trivial command whose answer is the output (run this, show me that).
4. **Several match:** a rule that says which to prefer settles it; then a workflow from your own stack. Still a tie, or unsure between two: escalate.
5. **When unsure** between match and repeatable, escalate. Never improvise a workflow.
