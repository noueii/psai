---
name: task-loop
description: "The end-to-end loop for any task that changes code, docs or config: clarify, size, implement, QA, verify, review, sanitize the PR. Use when you start such a task, whether or not it has a ticket, and when you decide how to delegate to Engineer, QA or Reviewer subagents."
---

# Task loop

You are the orchestrator. You plan, delegate and judge; the roles do the work. Escalate only by [escalation.md](escalation.md).

## 1. Clarify
Read the request, the repo's rules (AGENTS.md, CLAUDE.md, CONTRIBUTING) and `~/.harness/knowledge/INDEX.md`. Ask only what the escalation policy allows. Write the spec: goal, acceptance criteria, out of scope.

## 2. Size
- **Small**: clear, low-risk, contained. One shot, no plan acceptance.
- **Big**: multi-repo, API/schema/data changes, unclear or risky. Write a plan (steps, risks, test strategy) and iterate it with the human reviewer until they accept. Don't implement before acceptance.

## 3. Implement: Engineer
Delegate to a fresh subagent with [roles/engineer.md](roles/engineer.md) and the spec. When it returns, commit its work on the branch, so the next role starts from a clean tree.

## 4. Verification prep: QA
Delegate to a fresh subagent (never the Engineer's) with [roles/qa.md](roles/qa.md) and the spec, not the Engineer's notes. QA writes tests, E2E and other checks.

## 5. Verify
Run every check QA listed. Failures go back to step 3 with the failing output. Repeat until all pass; after two failed rounds on the same problem, escalate.

## 6. Review
- **AI review**: one or more fresh Reviewer subagents with [roles/reviewer.md](roles/reviewer.md), each with a different lens (correctness, spec fit, simplicity, security when relevant). Apply small fixes yourself, send rework back to step 3, escalate spec gaps.
- **Human review**: open or update the PR, ask for review, then handle comments the same way.

## Before merge
Use `sanitize-pr`. Never merge yourself. Throughout, use `capture-knowledge` for preferences and decisions.

## Delegation per tool
Always start the subagent with a FRESH context. The prompt is: "Read `~/.harness/skills/task-loop/roles/<role>.md` and follow it." plus the spec, the branch, the base commit and what to return.
- **Claude Code**: Agent (Task) tool, `subagent_type: general-purpose`.
- **opencode**: `task` tool, `subagent_type: general`.
- **omp**: `task` tool, agent `task`.
- **pi**: no subagents. Spawn a fresh process through bash: `pi -p --no-session "<prompt>"` (add `--mode json` to parse events). If that fails, run the role yourself, sequentially: re-read the role brief and work only from the spec.

## Role boundaries
Before each role starts, record `base=$(git rev-parse HEAD)` on a clean tree. After it finishes, run:

```sh
~/.harness/skills/task-loop/check-diff.sh <engineer|qa|reviewer> "$base"
```

QA may touch only tests and checks; the Reviewer may touch nothing. On a violation, revert that role's changes with `git reset --hard "$base" && git clean -fd` (safe because the tree was clean at `$base`) and re-run it with the violation quoted. A second violation: escalate.
