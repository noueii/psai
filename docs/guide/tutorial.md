# Tutorial: build your first stack

You will build `acme`, a tiny stack with one workflow ("make a change, test it, I approve, report"), publish it by pushing, and install it as a consumer in Claude Code, pi, omp and opencode. It takes about 20 minutes. Every `sh` block below runs as written. `scripts/prove-tutorial.sh` in psai runs them in order, in a temp HOME, against local git servers.

You need git, python3 with PyYAML (for the checks), and at least one of the tools. You also need two git URLs: psai's, and an empty repo you created for your stack.

```sh
export PSAI_GIT="${PSAI_GIT:-https://github.com/noueii/psai.git}"
export ACME_GIT="${ACME_GIT:-https://github.com/you/acme.git}"   # an empty repo you created, e.g. with `gh repo create you/acme --private`
export PSAI_STACK="$HOME/psai-stack"                              # where your stack's clone lives (this is the default)
```
Put the `PSAI_STACK` line in your shell profile too, so your tools see it.

## 1. Install psai
Pick one channel per tool (the [README](../../README.md) lists them all). Here, as the stack's author, use Claude Code:

```sh
claude plugin marketplace add "$PSAI_GIT"
claude plugin install psai@psai
```

Every new Claude Code session now gets the routing nudge and the six skills. Check with `claude plugin details psai@psai`.

You'll also want a clone of psai for its checks:

```sh
git clone -q "$PSAI_GIT" "$HOME/src/psai"
```

## 2. Let customize-harness bootstrap a workflow
In any repo, ask your agent:

> Set up my first workflow with customize-harness. Call the stack acme and the workflow change.

`customize-harness` asks one question at a time:
- which stack (none yet, so it offers to create `acme` at `$PSAI_STACK`);
- what tasks you hand to agents;
- the steps;
- the roles and what each may change;
- the checks;
- when to ask you;
- what the final report holds.

It offers design patterns, proposes the workflow, and builds it once you accept. This tutorial's answers are: a **maker** (may change anything) makes the change; a **tester** (may change tests only) adds tests and runs them, sending failures back to the maker at most twice; **you approve**; the agent writes a **report**.

To follow along without an agent, run what it does. First, the scaffold (the same commands as in customize-harness's SKILL.md):

```sh
S="$PSAI_STACK"; CH="$HOME/src/psai/skills/customize-harness"
mkdir -p "$S" && cp -R "$CH/template/." "$S/" && cd "$S"
for f in dot-*; do mv "$f" ".${f#dot-}"; done
grep -rl '__[A-Z]*__' . | xargs sed -i.bak -e 's/__NAME__/acme/g' -e 's|__REPO__|you/acme|g' -e 's/__DESCRIPTION__/Our team workflows/g' -e 's/__AUTHOR__/you/g'
find . -name '*.bak' -delete && git init -q -b main && git add -A && git commit -qm "acme: new psai stack"
```

Then the workflow skill. customize-harness writes it in the stage (a worktree of your stack, so nothing is live until you merge). By hand, write it straight into the clone:

```sh
W="$S/skills/workflow-acme-change"; mkdir -p "$W/steps" "$W/roles" "$W/templates"
cat > "$W/SKILL.md" <<'EOF'
---
name: workflow-acme-change
description: "Workflow: any task that changes files in a repo. Use when request-router picks it, or the owner asks for it by name."
---

# workflow-acme-change

A psai workflow: run it with the `work` skill. The state machine is [workflow.yaml](workflow.yaml); every file it names is relative to this folder, or `skill:path`.
EOF
cat > "$W/workflow.yaml" <<'EOF'
start: make
defaults: { max: 2, on_exhaust: escalate }
nodes:
  make:
    step: steps/make.md
    role: roles/maker.md
    next:
      - { when: blocked, to: escalate }
      - { to: test }
  test:
    step: steps/test.md
    role: acme-shared:roles/tester.md
    next:
      - { when: tests fail, to: make }
      - { when: done, to: approve }
  approve:
    step: steps/approve.md
    human: true
    next:
      - { when: changes requested, to: make }
      - { when: approved, to: report }
  report: { step: steps/report.md, next: [{ to: ready }] }
  escalate: { return: caller }
  ready: { terminal: true }
EOF
cat > "$W/steps/make.md" <<'EOF'
---
read: []
---
# Make
**In:** the task, or the tester's failures. **Out:** the change and a short note.

Make the smallest change that does what the task asks. **Edges:** `blocked` when the task can be read two ways and nothing settles it; otherwise the default.
EOF
cat > "$W/steps/test.md" <<'EOF'
---
read: []
---
# Test
**In:** the task and the diff. **Out:** `done`, or `tests fail` with the failures.

Add tests for what the task asks, then run the repo's tests.
EOF
cat > "$W/steps/approve.md" <<'EOF'
# Approve
Ask the human with a `review` block: summarise the change and the test results. Their answer selects `approved` or `changes requested`.
EOF
cat > "$W/steps/report.md" <<'EOF'
---
read: [templates/report.md]
---
# Report
Write the report (templates/report.md) as your final message.
EOF
cat > "$W/roles/maker.md" <<'EOF'
---
may_change: anything
---
# Role: maker
You make the change the step describes, starting fresh from the task and the repo. Don't commit; the orchestrator does.
EOF
mkdir -p "$S/evals/cases" && cat > "$S/evals/cases/workflow-acme-change.yaml" <<'EOF'
- name: straight through
  path: [make, test, approve, report, ready]
- name: blocked escalates
  take: { make: [blocked] }
  path: [make, escalate]
  asker: make
- name: the test loop is limited
  take: { test: [tests fail, tests fail, tests fail] }
  path: [make, test, make, test, make, test, escalate]
  asker: test
- name: my approval loop has no limit
  take: { approve: [changes requested, changes requested, changes requested, approved] }
  ends: ready
EOF
```

## 3. Add a role, a guide, a template and a skill
The tester is shared, so other workflows can use it: it goes in `acme-shared`, with a guide. The report template only this workflow uses, so it goes in the workflow's folder. And a skill of the stack's own, which the maker requires.

```sh
X="$S/skills/acme-shared"; mkdir -p "$X/roles" "$X/guides"
cat > "$X/SKILL.md" <<'EOF'
---
name: acme-shared
description: "Roles and guides that acme's workflows share. Use when a workflow, step or role names a file in acme-shared."
---
- `roles/tester.md`: adds tests from the task and runs them; may change tests only.
- `guides/testing.md`: how we write tests.
EOF
cat > "$X/roles/tester.md" <<'EOF'
---
may_change: tests
read: [guides/testing.md]
---
# Role: tester
You add tests from the task (not from the implementation) and run the repo's tests. Return `done` or `tests fail` with the failures.
EOF
cat > "$X/guides/testing.md" <<'EOF'
# Testing
- One test per behaviour the task asks for.
- Use the repo's own test runner.
EOF
cat > "$W/templates/report.md" <<'EOF'
# Report
## Summary
## Tests
## Open

## Example
# Report
## Summary
- Added `reverse(text)`.
## Tests
- `python3 -m unittest -q`: 5 tests pass.
## Open
- None.
EOF
mkdir -p "$S/skills/acme-changelog" && cat > "$S/skills/acme-changelog/SKILL.md" <<'EOF'
---
name: acme-changelog
description: "Adds one line per change to CHANGELOG.md at the repo root. Use when you change files in a repo."
---
After a change, append `- <what changed and why>` to CHANGELOG.md (create it if it's missing).
EOF
```

The maker requires that skill: name it in the role's frontmatter, so `work` checks it's installed before starting the role and lists it in the role's brief.

```sh
cat > "$W/roles/maker.md" <<'EOF'
---
may_change: anything
skills: { required: [acme-changelog] }
---
# Role: maker
You make the change the step describes, starting fresh from the task and the repo. Use the acme-changelog skill after each change. Don't commit; the orchestrator does.
EOF
```

Rules for every task go in a rules skill, which `request-router` loads first:

```sh
mkdir -p "$S/skills/acme-rules" && cat > "$S/skills/acme-rules/SKILL.md" <<'EOF'
---
name: acme-rules
description: "acme's rules for every task. Use when request-router starts on a request, before choosing a workflow."
---
- Ask before deleting files or changing a public API.
- Log every decision you take alone in the final report.
EOF
```

## 4. Set a model for a role
The tester's work is routine, so give it the fast tier. In Claude Code, `work` starts it with `haiku`; pi gets a per-tool id if you add one (`model: {claude: haiku, pi: <provider/id>}`):

```sh
cat > "$X/roles/tester.md" <<'EOF'
---
may_change: tests
model: fast
read: [guides/testing.md]
---
# Role: tester
You add tests from the task (not from the implementation) and run the repo's tests. Return `done` or `tests fail` with the failures.
EOF
```

## 5. Check it
psai's checks cover:
- every SKILL.md's frontmatter and the manifests;
- that every skill starts with `acme`;
- every ref, every node reachable and able to end, every loop limited;
- your simulator cases.

They run from your psai clone, and in CI on every push (`.github/workflows/psai.yml`):

```sh
"$HOME/src/psai/scripts/check.sh" "$S"
python3 "$HOME/src/psai/skills/customize-harness/graph.py" "$W" --write
```

The second line writes the workflow's diagram, `GRAPH.md`. To try the stack in Claude Code before you publish: `claude --plugin-dir "$S"` loads it for one session.

## 6. Publish by pushing
There is no build: the repo is the package. Commit, push, and tag a version.

```sh
cd "$S" && git add -A && git commit -qm "acme: the change workflow" && git tag v0.1.0
git remote add origin "$ACME_GIT" && git push -q -u origin main --tags
```

## 7. Install it as a consumer
On any machine (a teammate's, or yours), install psai and then the stack through the same channel, one channel per tool.

**Claude Code** (psai is already installed from step 1):

```sh
claude plugin marketplace add "$ACME_GIT"
claude plugin install acme@acme
```

**pi:**

```sh
pi install "$PSAI_GIT"
pi install "$ACME_GIT"
```

**omp:**

```sh
omp plugin install "$PSAI_GIT"
omp plugin install "$ACME_GIT"
```

**opencode** (and any other Agent Skills tool): copy the skills with `npx skills`, then add the nudge to `opencode.json`:

```sh
npx -y skills@latest add "$PSAI_GIT" -g -a opencode -y
npx -y skills@latest add "$ACME_GIT" -g -a opencode -y
mkdir -p "$HOME/.config/opencode" && [ -f "$HOME/.config/opencode/opencode.json" ] || echo '{ "instructions": ["~/.agents/skills/request-router/nudge.md"] }' > "$HOME/.config/opencode/opencode.json"
```

If you already have an `opencode.json`, add `"~/.agents/skills/request-router/nudge.md"` to its `instructions` list instead.

pi, omp and opencode all read `~/.agents/skills` too. On a machine where you use several of them, the `npx skills` copies and the pi or omp packages hold the same skills: each tool lists each skill once, but keep both up to date (step 8), or use `npx skills` alone for those tools and add the nudge to each one's instructions file.

Each tool now lists psai's six skills plus `workflow-acme-change`, `acme-shared`, `acme-rules` and `acme-changelog`. Give an agent a change to make in any repo: `request-router` loads `acme-rules`, matches `workflow-acme-change`, and `work` runs it.

## 8. Keep it updated
Change the stack the same way: ask an agent (customize-harness stages the change, and the retro opens one PR on your stack for you to merge), or edit by hand. Bump the version in `.claude-plugin/plugin.json`, `plugin.json` and `package.json` together, then push.

```sh
cd "$S" && cat >> "$X/guides/testing.md" <<'EOF'
- Name tests after the behaviour, not the function.
EOF
sed -i.bak 's/"version": "0.1.0"/"version": "0.2.0"/' .claude-plugin/plugin.json plugin.json package.json && find . -name '*.bak' -delete
git commit -qam "acme 0.2.0: test naming" && git tag v0.2.0 && git push -q origin main --tags
```

Consumers update through their channel, or ask an agent to run the `sync` skill, which does the same. omp updates a plugin installed from git by installing it again (`omp plugin upgrade` covers marketplace plugins only):

```sh
claude plugin marketplace update acme && claude plugin update acme@acme
pi update --extensions
omp plugin install "$PSAI_GIT" && omp plugin install "$ACME_GIT"
npx -y skills@latest update -g -y
```

A tool loads new skills in its next session.
