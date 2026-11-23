---
name: customize-harness
description: "Builds and changes the owner's psai setup WITH the owner, as skills in a stack: scaffolds their stack on first use, bootstraps a first workflow by interviewing them, or adds or changes one piece (workflow, step, role, guide, template, rules, skill, a role's model). Use when request-router finds no matching workflow and the owner agrees to set one up, when the owner wants to change how agents work or add a skill, or when a proposed-rule from an inbox is accepted."
---

# customize-harness

Below, `CH/` is this skill's folder. File everything per `CH/LAYOUT.md`, in the formats of `CH/FORMATS.md`. **Stage, never publish:** write in the stage `T` of the stack you change (the `work` skill's `your-stack.md`), never in the clone itself or in installed copies, which sessions read. Make no commit or PR yourself: the retro (or a `sync` node) at the end of the task finishes the stage as one PR the owner merges.

## How to ask
Ask the owner ONE question per message, with the fixed block (the `work` skill's `escalation.md`), kind `question`, node `customize`. Offer options with your recommendation first. Don't ask what the owner already told you or what LAYOUT.md settles.

## First: which stack?
- **Your own stack** (`$PSAI_STACK`, default `~/psai-stack`): recommend it for personal work.
- **Another stack you author:** its clone's path; use it as `S` instead.
- **None yet** (`S` isn't a git repo): ask for its name (lowercase, hyphens; it prefixes every skill) and where it will live (a GitHub repo `owner/name`, or local only), then scaffold it:
  ```sh
  mkdir -p "$S" && cp -R CH/template/. "$S/" && cd "$S"
  for f in dot-*; do mv "$f" ".${f#dot-}"; done
  grep -rl '__[A-Z]*__' . | xargs sed -i.bak -e 's/__NAME__/<name>/g' -e 's|__REPO__|<owner/name>|g' -e 's/__DESCRIPTION__/<one line>/g' -e 's/__AUTHOR__/<owner>/g'
  find . -name '*.bak' -delete && git init -q -b main && git add -A && git commit -qm "<name>: new psai stack"
  ```
  Then offer to create the GitHub repo (`gh repo create <owner/name> --private --source "$S" --push`) and say how to install it (its README). Unless `S` is `~/psai-stack`, tell the owner to set `PSAI_STACK="$S"` in their shell profile.

Someone else's stack is never edited: copy its workflow folder into your stack as `workflow-<yours>-<name>`, rename the skill, and change the copy.

## Bootstrap (no workflows yet)
1. **Interview** the owner about how they work, one question at a time. Cover EVERY topic below before proposing anything; skip a topic only if the owner already answered it:
   - what kinds of tasks they hand to agents;
   - the steps a task goes through, and where a human must look;
   - which roles exist and what each may change;
   - which checks prove the work is right;
   - when agents may decide alone and when they must ask;
   - what the final report of a task contains.
2. **Offer the design patterns** in [patterns/](patterns/) as options, one at a time and only where they fit. Never add one the owner didn't choose:
   - [separate roles](patterns/separate-roles.md)
   - [a checker that works from the spec](patterns/checker-from-spec.md)
   - [change limits enforced by diff](patterns/diff-limits.md)
   - [loop limits](patterns/loop-limits.md)
   - [sizing](patterns/sizing.md)
   - [a final report template](patterns/handover.md)
   - [a decide-and-log escalation policy](patterns/decide-and-log.md)
   - [end the workflow with retro, then sync](patterns/retro-sync-tail.md)
3. **Propose** the first workflow as a short summary: nodes, edges, roles and what each may change, models, human points, loop limits, attachments, rules for every task. Ask for acceptance; if the owner adds or corrects something, revise and ask again. Then build it (below).

## Add or change one piece
1. Ask what should change and why, if that isn't clear yet.
2. Ask the scope: every task (the `<stack>-rules` skill), one workflow (inside its folder), or several workflows (`<stack>-shared`). A rule for one repo only belongs in that repo's own AGENTS.md or docs: offer to write it there instead.
3. Pick the place and format from LAYOUT.md and FORMATS.md, and build it.

## Skills for a role or step
Name them in the file's frontmatter, `skills: {required: [...], optional: [...]}`. For each one: already in your tool's skill list, reference it by name. Someone else's: tell the owner how to install it through their tool's channel (its README), and name it. Doesn't exist: write it with the owner as `skills/<stack>-<name>/SKILL.md`, one question at a time.

## Build
1. In `T`, write the files. A workflow is `skills/workflow-<stack>-<name>/` with SKILL.md, `workflow.yaml` and `steps/`; put roles, guides and templates only it uses inside it, shared ones in `<stack>-shared`. A role's `model:` is a tier or ids per tool. For a new role, create `knowledge/roles/<role>/INDEX.md` (one-line title).
2. Rules for every task (an escalation policy, a preference) go in `skills/<stack>-rules/SKILL.md`, which the router loads first.
3. For a new workflow, also write its simulator cases `evals/cases/<workflow skill>.yaml` (every edge you added, every loop limit, every escalation) and one eval scenario `evals/scenarios/<name>.yaml` (the stack's `evals/README.md`).
4. Check your work: every ref resolves, every node is reachable from `start`, every path can end, every automatic loop has a limit, and walk each case by hand. With python3 and PyYAML, `python3 CH/graph.py <workflow folder> --write` writes its diagram (`GRAPH.md`); otherwise draw it yourself or skip it. The stack's CI runs psai's full checks when the PR is opened.
5. Leave it staged, and report what you staged. To try it before the PR merges, Claude Code can load the stage for one session: `claude --plugin-dir "$T"`. Once the owner merges the retro's (or sync's) PR, the stack's update command (its README) brings it to every tool.
