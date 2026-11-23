# Loop limits

**What:** every automatic loop (verify fails, rework) has a maximum; when it runs out, the agent escalates. Loops a human drives have no limit.
**Why:** an agent stuck on the same problem burns time and money, and needs a human after a couple of real tries.
**How:** `defaults: { max: 2, on_exhaust: escalate }` in the workflow, or `max:` on an edge. The maintainer checks (`scripts/check.sh`, your stack's CI) fail on an automatic back-edge without a limit.
