# Optional AI-judge rubric

Use this after the deterministic graders pass, when you want a quality read. Give a fresh agent the scenario file,
the final message and `git diff` of the work repo, and ask it to score each line from 0 to 2, with one sentence of
evidence each:

1. The change does what the task asked, and nothing else.
2. Tests cover the acceptance criteria and the edge cases the task implies.
3. The handover is accurate: every claim matches the diff and the check output.
4. Every decision made without asking is listed with a reason.
5. Escalations, if any, were necessary under the owner rules, and asked one clear question.

A run passes the judge at 8/10 or more. The judge never replaces the graders in `grade.py`.
