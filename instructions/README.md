# instructions/

`global.md` holds the framework's core rules. It opens the always-on nudge that each tool's plugin injects (`psai context`), and is kept at 120 words or fewer by check.sh. Your rules for every task go in your overlay's `instructions/owner.md` (`~/.psai/overlay/`), created by `customize-harness`; a stack's own short rules go in its `instructions/stack.md`. The nudge includes them, read live, so there's nothing to re-run after a change.
