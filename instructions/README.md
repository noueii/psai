# instructions/

`global.md` is the always-loaded core: imported into Claude Code and omp, and inlined into pi and opencode by `install.sh`. At most 250 words, enforced by check.sh. Owner rules that apply to every task go under `## Owner rules` (added by `customize-harness`). Re-run `install.sh` after changing it, so the inlined copies refresh.
