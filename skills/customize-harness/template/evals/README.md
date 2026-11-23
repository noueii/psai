# evals/

Maintainer-only tests for this stack's workflows; they don't ship. `cases/<workflow skill>.yaml` are simulator cases (scripted edges and the expected path; psai's `customize-harness` FORMATS.md), checked in CI. `scenarios/<name>.yaml` are optional AI eval scenarios, run only by hand with psai's `evals/run.sh --stack <this repo>` (a real model; never in CI). Example: `cases/workflow-<stack>-change.yaml`.
