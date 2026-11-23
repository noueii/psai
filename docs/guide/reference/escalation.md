# The fixed block

Every question to the human uses one block, so a person (or a script) can always find it: the `work` skill's `escalation.md`.

```
<<<HARNESS
kind: escalation
node: clarify
question: Should the separator be "-" or "_"?
why: The task says "better separators"; code and docs don't say which, and the answer changes the output.
options: ["-" (recommended), "_"]
>>>
```
- `kind`:
  - `escalation`: the agent can't or mustn't decide alone;
  - `review`: a human node;
  - `question`: a customize-harness interview question.
- `node`: the asking node (`route` in request-router, `customize` in customize-harness).
- One question per block. Put the recommended option first.

Agents escalate when no workflow fits a repeatable task, when a workflow edge or a loop limit sends them to `escalate`, and when your rules skill says so. Otherwise they decide, and log the decision in the final report and the knowledge inbox.
