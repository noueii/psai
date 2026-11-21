# psai harness

Harness root: `~/.harness`, or `$HARNESS_HOME` when it is set. Paths below are relative to that root.

- **Before you do anything for a task, read and follow the `work` skill.** It routes the task through `workflows/ROUTING.yaml` and runs the workflow it picks. Don't start the work yourself. If ROUTING.yaml is missing, there are no workflows yet.
- **Built-in rule:** if no workflow matches, or you are unsure which one does, escalate in the fixed format (`skills/work/escalation.md`). Never improvise a workflow.
- **The owner's setup** (workflows, steps, roles, guides, templates) lives where `LAYOUT.md` says. Change it only with the `customize-harness` skill, as a PR the owner approves.
- **During a task, write only to:**
  - the knowledge inboxes (`capture-knowledge` skill);
  - the task's own PR description or final report.
- **Precedence, most specific wins:**
  1. the repo's `.harness/` folder;
  2. the current step or role and its `read:` files;
  3. this file.

Your own rules for every task live in `instructions/owner.md`. When it exists, install.sh loads it along with this file.
