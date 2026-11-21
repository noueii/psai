# Plan: <task>

## Steps
1. ...
## Risks
## Test strategy

## Example
# Plan: move sessions to Postgres
## Steps
1. Add the `sessions` table (migration 0042).
2. Dual-write for one release, then switch reads.
## Risks
- Migration lock on a large table: run it off-peak.
## Test strategy
- Migration up/down test; integration test for dual-write.
