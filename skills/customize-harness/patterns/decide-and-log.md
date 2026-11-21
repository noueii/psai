# A decide-and-log escalation policy

**What:** agents escalate only in listed cases and otherwise decide, logging each decision and its reason.
**Why:** a fully autonomous agent that asks about everything isn't autonomous; one that never asks takes risks the owner didn't accept.
**How:** list the cases under `## Owner rules` in `instructions/global.md`. Common cases: an unclear requirement whose answer changes the outcome, an irreversible or visible action, a rule conflict, still stuck after two tries, scope growing well beyond the ask. Decisions go in the handover and the knowledge inbox.
