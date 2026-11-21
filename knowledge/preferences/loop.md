# The loop

For every task (not necessarily a ticket):
1. Clarify, asking only what the escalation policy allows.
2. Size it. Small (clear, low-risk, contained): one shot, no plan acceptance. Big (multi-repo, API/schema/data changes, unclear or risky): write a plan and iterate it with the human reviewer until they accept.
3. Implement (Engineer).
4. Verification prep: tests, E2E and other checks (QA, a different agent from the Engineer, working from the spec).
5. Verify loop; failures go back to 3.
6. AI review loop with one or more Reviewers using different lenses: small fixes get applied, rework goes back to 3, spec gaps escalate. Then the human review loop, same process.

- Before merge: sanitize the PR to the owner's preferences and the repo's rules. Never merge yourself.
- Throughout: capture preferences and decisions as knowledge.

Source: [decision 2026-11-21-the-loop](../decisions/2026-11-21-the-loop.md).
