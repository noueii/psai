# Change limits enforced by diff

**What:** each role declares what it may change, and the engine checks the git diff after it finishes.
**Why:** a checker that edits product code, or a reviewer that edits anything, defeats the point of separate roles.
**How:** `may_change: anything | tests | nothing` in the role's frontmatter. `skills/work/check-diff.sh` enforces it; a violation is reverted and the role re-run once, then escalated.
