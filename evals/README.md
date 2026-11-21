# evals/

AI evals that run the harness headless, so the owner isn't the test loop.
- **L3:** scenarios on the test content in `fixtures/harness-content/`, plus one on vanilla.
- **L4:** a generic user bootstraps a workflow from vanilla with `customize-harness`; then a fixture task runs on the result.

```sh
evals/run.sh                                    # every scenario, Claude Code, 1 run each
evals/run.sh --runs 3 evals/scenarios/psai/happy-path.yaml
evals/run.sh --tool all                         # Claude Code and omp
```

## How a run works
`driver.py` builds a throwaway directory per run:
- **harness copy:** a copy of this harness, with the scenario's `content` overlaid;
- **fixture repo copy:** its `origin` is a local bare repo;
- **`gh` shim:** refuses every call.

It then starts the tool headless with the harness loaded for that run only:
- **Claude Code:** `--plugin-dir`, `--append-system-prompt-file`, `--setting-sources project`, `--no-session-persistence`;
- **omp:** `--config` with `skills.customDirectories` and user skill folders off, plus `--append-system-prompt`.

`HARNESS_HOME` points at the harness copy. Nothing is installed into the real HOME and no credentials are copied: each tool reads its own login in place. pi and opencode are skipped when they have no working provider.

A scripted **fake owner** answers each fixed block (`skills/work/escalation.md`) from the scenario file:
- `review`: answered with `owner.review`;
- `question` and `escalation`: the first `match` regex wins.

A block with no scripted answer is an unexpected escalation and fails the run.

## Results
`graders/grade.py` checks:
- the printed `[harness] node:` path;
- per-role `check-diff` results (`HARNESS_TRACE`);
- that the repo's checks pass;
- the final report's sections;
- the escalation count;
- for L4, that customize-harness touched only user-owned paths;
- that nothing was pushed or merged.

Each run writes a JSON summary to `results/`. A passing L4 run also saves the harness content it built. `--runs N` gives a pass rate. `graders/judge.md` is an optional AI-judge rubric.

Scenario format: see [scenarios/README.md](scenarios/README.md).
