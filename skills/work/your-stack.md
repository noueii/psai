# Your stack

Your own psai content (workflows, roles, guides, templates, rules, skills) and your knowledge live in one git repo you own: **your stack**. Its working copy is `$PSAI_STACK`, or `~/psai-stack` when that isn't set:

```sh
S="${PSAI_STACK:-$HOME/psai-stack}"
```

If `$S` isn't a git repo, you have no stack yet. Offer to create one with `customize-harness` (fixed block, kind `question`); never create it unasked. Its layout is the `customize-harness` skill's `LAYOUT.md`.

## Knowledge
Knowledge lives in `$S/knowledge/`. Inboxes (`knowledge/inbox.md`, `knowledge/roles/<role>/inbox.md`) are edited in place in `$S` and stay uncommitted until the retro promotes them.

## The stage
Every other change (customize-harness, the retro, sync) is made in the **stage**: a git worktree of your stack on the branch `psai/stage`. Never edit `$S` itself, because your tools may read it live.

```sh
T="$(git -C "$S" rev-parse --path-format=absolute --git-common-dir)/psai-stage"
[ -d "$T" ] || git -C "$S" worktree add -q "$T" -B psai/stage
```

## Finish (the retro or sync does this, once per task)
1. `git -C "$T" add -A`. If `git -C "$T" diff --cached --quiet` succeeds, nothing is staged: `git -C "$S" worktree remove "$T"` and stop.
2. Commit and name the branch: `git -C "$T" commit -qm "psai: <summary>"`, then `git -C "$T" branch -m "psai/$(date +%Y%m%d-%H%M)-<slug>"`.
3. With an `origin` remote and `gh` logged in: `git -C "$T" push -u origin <branch>`, then `gh pr create --head <branch> --title "<title>" --body-file <report>` from `$S`. Otherwise keep the branch and say where it is.
4. `git -C "$S" worktree remove "$T"`. Never merge the PR: the owner does.
