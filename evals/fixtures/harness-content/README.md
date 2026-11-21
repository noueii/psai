# evals/fixtures/harness-content/

Neutral TEST content: one tiny `example` workflow, with generic roles (`doer` may change anything, `checker` nothing), steps, a guide, a template and role knowledge. It is just big enough to exercise every feature:
- `read:` attachments;
- `may_change`;
- a required skill (`doer` needs `my-skills/change-notes`);
- a limited loop;
- a human gate;
- escalate;
- ready.

It's never installed. Tests overlay it on a throwaway copy of the vanilla harness:
- `scripts/check.sh` and `scripts/simulate.py` validate it (L0, L2);
- the L3 eval scenarios run on it.

The tree mirrors the harness root, so every file follows `LAYOUT.md`.
