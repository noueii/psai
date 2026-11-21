# Layout: where things go

`customize-harness` and `capture-knowledge` file everything by this table, and `scripts/check.sh` fails on any file under `workflows/ steps/ roles/ guides/ templates/ knowledge/` whose path doesn't match the **Goes in** column (`<x>` matches one path segment).

| You're adding | Goes in | Format |
|---|---|---|
| a workflow | `workflows/<name>.yaml` | state machine, see workflows/README.md |
| its simulator cases | `workflows/<name>.cases.yaml` | scripted outcomes and the expected path |
| a route to a workflow | `workflows/ROUTING.yaml` | a branch of the decision tree |
| a step | `steps/<name>.md` | frontmatter `read:` + prose |
| a role | `roles/<name>.md` | frontmatter `may_change:`, `read:` + prose |
| a role's knowledge | `knowledge/roles/<role>/INDEX.md` and `knowledge/roles/<role>/inbox.md` | index and inbox |
| a rule for one kind of work | `guides/<name>.md` | prescriptive prose, attached with `read:` |
| an output format | `templates/<name>.md` | the format, then a filled-in example |
| a rule for every task | `instructions/global.md` | a line under `## Owner rules` |
| a finding during a task | `knowledge/inbox.md` or `knowledge/roles/<role>/inbox.md` | dated entry, see capture-knowledge |
| a promoted fact | `knowledge/facts/<topic>.md` | prose with sources |
| a promoted decision | `knowledge/decisions/<date>-<slug>.md` | Decision / Why / Source |
| the knowledge index | `knowledge/INDEX.md` | one line per file |
| an eval scenario | `evals/scenarios/<name>.yaml` | see evals/README.md |
| a rule for one repo only | `<repo>/.harness/<same path as above>` | same format; created on first use; wins over the shared file |

Folder READMEs (`<folder>/README.md`) describe each folder and are always allowed.

Precedence, most specific wins: `<repo>/.harness/` > the step or role and its `read:` files > `instructions/global.md`.
