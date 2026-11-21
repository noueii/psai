# Separate roles

**What:** different fresh agents implement, check and review, instead of one agent doing everything.
**Why:** a fresh agent doesn't inherit the implementer's assumptions or blind spots.
**How:** one `roles/<name>.md` per role, used by `role:` nodes. Typical set: engineer (implements), qa (writes checks), reviewer (reviews through lenses with `fan_out`).
