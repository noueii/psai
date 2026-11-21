# A decide-and-log escalation policy

**What:** agents escalate only in listed cases and otherwise decide, logging each decision and its reason.
**Why:** a fully autonomous agent that asks about everything isn't autonomous; one that never asks takes risks the owner didn't accept.
**How:** ask the owner which cases need a human, and list them in `instructions/owner.md`. Decisions made without asking go in the final report and the knowledge inbox.
