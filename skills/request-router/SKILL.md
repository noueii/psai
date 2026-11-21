---
name: request-router
description: "Decides how to handle a request: runs one of the owner's workflows, offers to create one, or handles it directly. Reads workflows/ROUTING.yaml and the workflows live. Use first for every request, except a quick question or a one-off reply."
---

# request-router

`H` is the harness root: `$HARNESS_HOME` if set, else `~/.harness`.

1. **Read the router.** Walk the tree in `H/workflows/ROUTING.yaml`: at each `ask`, pick the answer (`if`) that fits the request and follow its `then`. Also read each workflow's `when` (`H/workflows/*.yaml`). The file may be missing: then there are no workflows yet.
2. **Decide:**
   - **Match** (a `workflow:` leaf, or a workflow whose `when` fits, even if the request doesn't name it): read the engine `H/skills/work/SKILL.md` and run that workflow from its `start`. Don't do any of the work before that.
   - **No match, but repeatable** (a kind of task that will come back, and could become a workflow): escalate with the fixed block (`H/skills/work/escalation.md`), with kind `escalation` and node `route`, offering to create a workflow with `customize-harness`.
   - **No match, one-off** (a quick question, a one-time action): handle it normally, with no workflow and no escalation.
3. **When unsure** between match and repeatable, escalate. Never improvise a workflow.
