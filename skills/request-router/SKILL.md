---
name: request-router
description: "Decides how to handle a request: runs one of the owner's workflows, offers to create one, or handles it directly. Reads the routing trees and the workflows live (`psai route`). Use first for every request, except a quick question or a one-off reply."
---

# request-router

Run `psai` as the nudge says if it isn't on PATH.

1. **Read the router.** Run `psai route`. It prints each stack's routing tree and its workflows' `when`, and where the engine and the escalation block are. Walk the tree: at each `ask`, pick the answer (`if`) that fits the request and follow its `then`. It may list no workflows yet.
2. **Decide:**
   - **Match** (a `workflow:` leaf, or a workflow whose `when` fits, even if the request doesn't name it): read the engine (the `work` skill) and run that workflow from its `start`. Don't do any of the work before that.
   - **No match, but repeatable**: escalate with the fixed block, with kind `escalation` and node `route`, offering to create a workflow with `customize-harness`.
   - **No match, one-off**: handle it normally, with no workflow and no escalation.

   Judge the **kind** of work, not this one request. Changing code or docs (a feature, a fix, a helper, a refactor), reviews, reports and recurring chores are repeatable kinds, even the first time one is asked. One-off means a question, an explanation, or a trivial command whose answer is the output (run this, show me that).
3. **When unsure** between match and repeatable, escalate. Never improvise a workflow.
