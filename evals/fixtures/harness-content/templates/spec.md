# Spec: <task>

## Goal
## Acceptance criteria
- [ ] ...
## Out of scope
## Decisions made while clarifying

## Example
# Spec: truncate()
## Goal
Add `truncate(text, n)` to textkit.
## Acceptance criteria
- [ ] Returns `text` unchanged when `len(text) <= n`.
- [ ] Otherwise returns the first `n - 1` characters plus "…" (length `n`).
- [ ] `n < 1` raises `ValueError`.
## Out of scope
Word-boundary truncation.
## Decisions made while clarifying
- The result includes the "…" in its length `n`, because callers size columns by `n`.
