# evals/scenarios/

One YAML file per scenario, `<name>.yaml`; the format is psai's `evals/scenarios/README.md`. A scenario here runs with this stack installed, so its `stacks:` key is filled in by `psai eval`. Example:
```yaml
name: review-happy-path
level: L3
fixture: textkit
task: Review the last commit of this repo.
owner: { review: Approved., max_turns: 6 }
expect: { router_invoked: true, path_includes: [review, ready], escalations: { max: 0 } }
```
