# instructions/

`global.md` holds the core rules. It opens the always-on nudge that each tool's plugin injects (`scripts/harness.py context`), and is kept at 120 words or fewer by check.sh. It is upstream-owned. Your rules for every task go in `owner.md`, which is yours and created by `customize-harness`; the nudge includes it. Plugins read both files live, so there's nothing to re-run after a change.
