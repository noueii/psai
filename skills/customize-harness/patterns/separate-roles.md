# Separate roles

**What:** different fresh agents implement, check and review, instead of one agent doing everything.
**Why:** a fresh agent doesn't inherit the implementer's assumptions or blind spots.
**How:** one `roles/<name>.md` per role, used by `role:` nodes. For example, one role that makes the change and another that checks it; `fan_out` runs one agent per lens.
