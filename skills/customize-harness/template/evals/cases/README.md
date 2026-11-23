# evals/cases/

One file per workflow, `<workflow skill>.yaml`: a list of `{name, take, ends, asker?, path?}` cases (psai's `customize-harness` FORMATS.md). CI fails when a workflow has none or a case's path differs. Example: `workflow-<stack>-change.yaml`.
