# evals/scenarios/

One YAML file per scenario, named `<name>.yaml`; `customize-harness` adds at least one for every new workflow. Example: [happy-path.yaml](happy-path.yaml). Format:
```yaml
name: happy-path
level: L3                      # L3 (content fixture) or L4 (bootstrap)
content: harness-content       # folder in evals/fixtures/ overlaid on the harness; null = vanilla
fixture: textkit               # fixture repo in evals/fixtures/
task: ...                      # the prompt
owner:                         # the fake owner
  review: Approved.            # answer to kind: review
  escalations: [{ match: <regex>, answer: ... }]
  answers: [{ match: <regex>, answer: ... }]   # kind: question (customize-harness)
  default: ...                 # fallback for questions only
  max_turns: 6
expect: { ... }                # assertions, listed in evals/graders/grade.py
```
A multi-step scenario uses `phases: [{ name, cwd: harness|fixture, task, owner, expect }]`; later phases run on the harness that earlier phases built.
