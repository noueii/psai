# A stack

A stack is a git repo of skills, laid out like psai itself, so it installs through the same channels. `customize-harness` scaffolds one from its `template/` folder.

```
acme/
  .claude-plugin/plugin.json        Claude Code plugin: name, version, description
  .claude-plugin/marketplace.json   the repo as its own Claude Code marketplace (one plugin, source "./")
  plugin.json                       Agent Plugins 1.0 manifest (omp and other Agent Plugins clients)
  package.json                      pi package ("pi": { "skills": ["./skills"] }); omp reads it too
  .github/workflows/psai.yml        CI: psai's checks on every push
  README.md                         what it is and how to install it
  skills/                           everything that ships
    workflow-acme-change/           a workflow
    acme-shared/                    roles, guides, templates several workflows share
    acme-rules/                     rules for every task
    acme-changelog/                 a skill of the stack's own
  knowledge/                        your knowledge (only in your own stack; never ships)
  evals/cases/, evals/scenarios/    simulator cases and eval scenarios (never ship)
```

## Names
The stack's name is the `name` in its manifests: lowercase letters, digits and single hyphens. **Every skill a stack ships starts with it**: `acme-…`, or `workflow-acme-…` for a workflow. Tools merge the skills of everything you install into one list, so this prefix is what keeps two stacks from colliding. Claude Code also shows plugin skills as `acme:workflow-acme-change`. The checks fail on a skill without the prefix.

## Versions and publishing
The three manifests carry the same version (the checks fail otherwise). To publish, bump all three, commit, push, and optionally tag `vX.Y.Z`. There is no build: consumers install the repo as it is.

## CI
`.github/workflows/psai.yml` checks out psai and runs `scripts/check.sh .` on the stack:
- frontmatter;
- manifests;
- READMEs;
- names;
- workflow refs, graph rules and simulator cases.

Pin `ref:` to a psai tag for repeatable runs. When your stack names files in another stack (`other-shared:…`), check out that stack too and add `--with <path>`.
