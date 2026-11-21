# evals/results/

Local output only. Everything in this folder except this README is git-ignored.

Each run writes one summary, `<time>-<scenario>-<tool>.json`, with the path taken, escalations, check results, time and cost. It never writes transcripts. A passing L4 run also saves the harness content it built, in `<time>-<scenario>-<tool>-content/`.

To share a result, put the pass rates in the PR description rather than committing the files.
