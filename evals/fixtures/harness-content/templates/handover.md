# Handover

## What changed
## How it was verified
## Decisions made without you
## Open, needs you

## Example
# Handover
## What changed
- `textkit/text.py`: new `truncate(text, n)`; README documents it.
## How it was verified
- `python3 -m unittest -q`: 9 tests pass, including 4 new QA tests for truncate.
## Decisions made without you
- "…" counts toward `n`: callers size columns by `n`.
## Open, needs you
- Nothing. Ready for your review; not merged.
