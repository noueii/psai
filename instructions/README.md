# instructions/

`global.md` is the always-loaded core: imported into Claude Code and omp, and inlined into pi and opencode by `install.sh`. At most 250 words, enforced by check.sh. It is upstream-owned: your rules for every task go in `owner.md` (yours; created by `customize-harness`), which install.sh loads along with `global.md`. Re-run `install.sh` after changing either, so the inlined copies refresh.
