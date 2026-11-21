# knowledge/

What's true and what was decided and why: descriptive, dated, sourced. This is the stack author's curated knowledge; it ships with the stack. Users' findings never land here directly: their inboxes live in their own overlay (`~/.psai/overlay/knowledge/<stack>/`), and a role reads this stack's index first, then the user's (knowledge is additive, never overridden).

- `INDEX.md`: one line per file.
- `facts/<topic>.md`: facts, with sources.
- `decisions/<date>-<slug>.md`: decisions (Decision / Why / Source).
- `roles/<role>/INDEX.md`: per-role knowledge, created with each role.
