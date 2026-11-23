# evals/scenarios/

psai's own scenarios live in [psai/](psai/README.md); a stack keeps its own in its `evals/scenarios/` (`evals/run.sh --stack <repo>`), and `customize-harness` adds one for every new workflow there. Running them is optional and manual (they use a real model). Example: [psai/happy-path.yaml](psai/happy-path.yaml). Format:
```yaml
name: happy-path
level: L3                      # L3 (content fixture) or L4 (bootstrap)
stacks: { example: stacks/example }   # loaded as plugins: a folder in evals/fixtures/, or a list copied over each other in order
own: none                      # optional: no owner's stack (default: `mine`, scaffolded from the template); or a list of fixture folders copied over it
strip: [stacks/example/skills/example-change-notes]   # optional: remove a path from the run's copies
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
A multi-step scenario uses `phases: [{ name, cwd: own|fixture, merge: true, task, owner, expect }]`. With `merge: true`, the owner's stack merges what the phase staged before grading, and later phases load the result.
