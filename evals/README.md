# evals/

Maintainer-only AI evals: they run psai headless in Claude Code, so the owner isn't the test loop. They cost money: run few, and only where behaviour changes. Never shipped.
- **L3:** scenarios with test stacks from `fixtures/stacks/` loaded (`example`, `other`), or none.
- **L4:** a generic user bootstraps their own stack and first workflow with `customize-harness`; then a fixture task runs on the result.

```sh
evals/run.sh evals/scenarios/psai/happy-path.yaml       # one scenario, sonnet, 1 run
evals/run.sh --runs 3 --model opus <scenario>
evals/run.sh --stack ~/src/acme                         # a stack's own evals/scenarios/, with that stack loaded
```

## How a run works
`driver.py` builds a throwaway directory per run, the way a consumer installs psai 4:
- `psai/`: the shipped part of this repo (skills, manifests, hooks), with no scenarios or graders, so the agent never sees the expected answers;
- `stacks/<name>/`: copies of the scenario's `stacks:`;
- `own/`: the owner's stack (`PSAI_STACK`), scaffolded from customize-harness's template as `mine` (or absent with `own: none`);
- `work/`: a copy of the fixture repo, whose `origin` is a local bare repo;
- a `gh` shim that refuses every call.

It starts `claude -p` with `--plugin-dir` for psai, each stack and the owner's stack (when it has skills), `--setting-sources project` and `--no-session-persistence`. That is the same plugin a real install uses, including the SessionStart nudge, but it is loaded for the run only. Nothing is installed into the real HOME and no credentials are copied: Claude Code reads its own login in place. The raw event stream is saved as `stream.jsonl` (`--keep` keeps the directory).

A scripted **fake owner** answers each fixed block (`skills/work/escalation.md`) from the scenario file:
- `review`: answered with `owner.review`;
- `question` and `escalation`: the first `match` regex wins.

A block with no scripted answer is an unexpected escalation, and fails the run.

## Results
`graders/grade.py` checks:
- the traced path and the per-role `check-diff` results (`PSAI_TRACE`);
- the repo's checks and the final report's sections;
- escalations;
- what was staged in the owner's stack;
- that psai and the stacks are untouched;
- that nothing was pushed or merged.

Each run writes a JSON summary to `results/` (git-ignored). Report pass rates in the PR. A passing L4 run also saves the stack it built. Scenario format: [scenarios/README.md](scenarios/README.md).
