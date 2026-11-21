# migrations/

One-time upgrade steps for a machine, run once each by `install.sh` (and so by `psai update` and the sync skill). Upstream-owned. Name: `NNNN-<slug>.sh`, numbered in order; never renumber or edit one that shipped, add a new one instead. The runner (`scripts/sync.py migrate`) records each one it ran in `.state/migrations.json`, so it runs once per machine; a failing script exits non-zero and runs again next time.

A script gets `PSAI_LINK` (the base link, `~/.psai` or `$PSAI_HOME`), `PSAI_REPO` (the clone) and `DRY_RUN` (`1`: only print `would: ...`). It must be idempotent and touch only psai's own files. Example: [0001-remove-old-harness-link.sh](0001-remove-old-harness-link.sh).
