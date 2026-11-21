# __NAME__

__DESCRIPTION__

A [psai](https://github.com/noueii/psai) stack. Add it to a machine where psai is installed:
```sh
psai stack add <this repo's URL or github:owner/repo>
```

## Workflows
Each workflow's diagram is in [workflows/GRAPHS.md](workflows/GRAPHS.md) (`psai graph . --update-readme` writes it).

## Develop it
`psai new-stack` installed this stack in dev mode: psai reads your working clone. Check it with `psai check .` (also in CI), and try its eval scenarios with `psai eval .`. `psai publish` tags a release.
