# psai harness

Harness root: `~/.harness`, or `$HARNESS_HOME` when it is set. Paths below are relative to that root.

- **For any task, use the `work` skill.** It routes the task through `workflows/ROUTING.yaml` and runs the workflow it picks.
- **Built-in rule:** if no workflow matches, or you are unsure which one does, escalate in the fixed format (`skills/work/escalation.md`). Never improvise a workflow.
- **The owner's setup** (workflows, steps, roles, guides, templates) lives where `LAYOUT.md` says. Change it only with the `customize-harness` skill, as a PR the owner approves.
- **During a task, write only to:**
  - the knowledge inboxes (`capture-knowledge` skill);
  - the task's own PR description or handover.
- **Precedence, most specific wins:**
  1. the repo's `.harness/` folder;
  2. the current step or role and its `read:` files;
  3. this file.

## Owner rules
Escalate only when:
- a requirement is unclear AND the answer changes the outcome, and code, docs and knowledge can't settle it;
- the action is irreversible or visible to others (merge, deploy, posting to people, deleting what isn't yours);
- it goes against a stated rule or preference, or two rules conflict;
- you're still stuck after two real attempts;
- the scope grows well beyond what was asked.

Otherwise decide, and log the decision and its reason in the handover (or PR description) and the knowledge inbox. Never merge.
