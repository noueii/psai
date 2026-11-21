# 0007: Built to be forked (2026-11-21)
- Decision: users fork psai and build their stack in the fork. LAYOUT.md marks every path as user- or upstream-owned:
  - psai never ships user-owned files: no ROUTING.yaml, knowledge index or inbox, `instructions/owner.md` or `workflows/GRAPHS.md`;
  - `customize-harness` writes only user-owned paths;
  - the installer works from any clone path and loads `owner.md` next to `global.md`.

  `check.sh --upstream` and an L1 fork-merge test enforce this.
- Why: pulling upstream updates into a fork must not conflict with the user's own setup.
- Source: v2 design review.
