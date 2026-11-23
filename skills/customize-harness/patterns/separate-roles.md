# Separate roles

**What:** different fresh agents implement, check and review, instead of one agent doing everything.
**Why:** a fresh agent doesn't inherit the implementer's assumptions or blind spots.
**How:** one role file per role (`roles/<name>.md` in the workflow's folder, or in `<stack>-shared` when several workflows use it), used by `role:` nodes. For example, one role that makes the change and another that checks it; `fan_out` runs one agent per lens.
