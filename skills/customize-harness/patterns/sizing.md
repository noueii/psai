# Sizing

**What:** classify each task as small (clear, low-risk, contained: one shot) or big (multi-repo, API/schema/data changes, unclear or risky: a plan the human accepts first).
**Why:** small tasks shouldn't wait on a plan review; big ones shouldn't start without one.
**How:** a clarify step that ends with `when: big -> plan` and a default edge to implementation; a `plan` node followed by a `human: true` plan review that loops until accepted.
