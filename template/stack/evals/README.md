# evals/

This stack's AI eval scenarios and their fixture repos. `psai eval .` runs them headless in a temp psai home with the framework, this stack and its `requires:` (no overlay, never the real HOME); results stay local.
- `scenarios/<name>.yaml`: one per scenario (format: psai's `evals/scenarios/README.md`); at least one per workflow.
- `fixtures/<name>/`: a small repo a scenario's `fixture:` names (psai's own fixtures, such as `textkit`, also work).
