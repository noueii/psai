# schemas/

JSON Schemas for the files psai reads from stacks. `scripts/resolve.py` validates them with the subset of JSON Schema they use (no extra dependency), and `psai check` runs it. Name: `<file>.schema.json`. Example: [stack.schema.json](stack.schema.json), the format of a stack's `stack.yaml` (ADR 0011, section 2).

Two keywords are psai's own: `maxWords` (a word cap on a string) and `format: version-range` (comparators such as `>=3.0 <4`).
