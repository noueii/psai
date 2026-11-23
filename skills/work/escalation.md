# The fixed block

Every question to the human uses this block, exactly. Put it at the end of your message, then stop and wait. The human's next message is the answer; resume where you asked.

```
<<<HARNESS
kind: escalation
node: clarify
question: Should the separator be "-" or "_"?
why: The task says "better separators"; code and docs don't say which, and the answer changes the output.
options: ["-" (recommended), "_"]
>>>
```

- `kind` is one of:
  - `escalation`: you can't or mustn't decide alone;
  - `review`: a human node asks for approval or changes;
  - `question`: a `customize-harness` interview question.
- `node` is the workflow node that asks. Use `route` in request-router and `customize` in `customize-harness`.
- `question` holds ONE question. `options` is optional; put your recommendation first.
- `why` says why code, docs and knowledge can't settle it, or names the rule that requires asking.

## When to escalate
- No workflow matches a repeatable task, or you're unsure whether one does (offer `customize-harness`). A one-off with no match needs no escalation.
- A workflow edge sends you to `escalate`, or a loop runs out of tries.
- Anything the rules in your stack's `*-rules` skill list.

Otherwise decide. Log the decision and its reason in the final report, and add it to the knowledge inbox with the `capture-knowledge` skill.
