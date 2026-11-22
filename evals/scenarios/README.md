# evals/scenarios/

psai's own scenarios live in [psai/](psai/README.md); a stack keeps its own in its `evals/scenarios/` (`psai eval <stack>`), and `customize-harness` adds one for every new workflow there. Example: [psai/happy-path.yaml](psai/happy-path.yaml). Format:
```yaml
name: happy-path
level: L3                      # L3 (content fixture) or L4 (bootstrap)
stacks: { example: stacks/example, other: stacks/other }   # installed in the run's home: a folder in evals/fixtures/, or a list overlaid in order
strip: [stacks/example/my-skills]   # optional: hide paths (in the home for stacks/ and overlay/, else in the framework copy)
overlay: stacks/nostack        # with stacks: the overlay's fixture (default: an empty overlay)
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
A multi-step scenario uses `phases: [{ name, cwd: harness|fixture, task, owner, expect }]` (`harness` is the overlay); later phases run on what earlier phases built.
