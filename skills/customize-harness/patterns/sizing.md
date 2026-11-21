# Sizing

**What:** classify each task as small (one shot) or big (a plan the human accepts first), by criteria the owner picks.
**Why:** small tasks shouldn't wait on a plan review; big ones shouldn't start without one.
**How:** a clarify step that ends with `when: big -> plan` and a default edge to implementation; a `plan` node followed by a `human: true` plan review that loops until accepted.
