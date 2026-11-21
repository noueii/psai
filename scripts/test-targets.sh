#!/usr/bin/env bash
# L1 tests for retro and sync in the stacks layout (ADR 0011, sections 7 and 14): per-target stages and PR branches
# (your overlay, a dev stack), suggestions for a pinned stack's author (drafted, opened only when asked), newer
# framework and stack releases in the check, the overlay's ff-only update with the inbox union, and a framework
# update refused while a stack doesn't support it. Temp HOMEs, local bare git remotes, no network, no AI.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
FIX="$ROOT/evals/fixtures/harness-content"
[ -d "$FIX" ] || exit 0
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
unset PSAI_HOME PSAI_STATE PSAI_TRACE PSAI_ROLE PSAI_EVAL XDG_CONFIG_HOME
export PSAI_HOST=box GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
fails=0
pass() { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; fails=$((fails + 1)); }
check() { local msg="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$msg"; else fail "$msg"; fi; }
today="$(date +%Y%m%d)"; V="$(cat "$ROOT/VERSION")"

# the framework: a release-tagged clone (so it can be fast-forwarded), an example stack (pinned) and a dev stack
fws="$T/fwsrc"; mkdir -p "$fws"; (cd "$ROOT" && git ls-files -co --exclude-standard -z | xargs -0 cp --parents -t "$fws")
(cd "$fws" && git init -q -b main && git add -A && git commit -qm fw && git tag "v$V" && git clone -q --bare . "$T/fw.git")
ex="$T/ex"; mkdir -p "$ex"; cp -r "$FIX"/. "$ex/"; (cd "$ex" && git init -q -b main && git add -A && git commit -qm one && git tag v1.0.0)
echo "- a 1.1 rule" >> "$ex/guides/example-rules.md"; sed -i 's/^version: 1.0.0/version: 1.1.0/' "$ex/stack.yaml"; (cd "$ex" && git commit -qam two && git tag v1.1.0)
git clone -q --bare "$ex" "$T/mine.git"; wk="$T/mine"; git clone -q "$T/mine.git" "$wk"; git -C "$wk" checkout -q v1.0.0 -b work
sed -i 's/^name: example/name: mine/' "$wk/stack.yaml"; (cd "$wk" && git commit -qam "my stack" && git push -q -u origin work)
h="$T/h"; H="$h/.psai"; mkdir -p "$H" "$h/.claude"; git clone -q "$T/fw.git" "$H/framework"
HOME="$h" bash "$H/framework/install.sh" > /dev/null 2>&1 || fail "install from a framework clone"
git init -q --bare "$T/ov.git"; (cd "$H/overlay" && git remote add origin "$T/ov.git" && git push -q -u origin main)
ps() { (cd "$T" && HOME="$h" python3 "$H/framework/scripts/psai.py" "$@"); }
ps stack add "$ex" --ref v1.0.0 --yes > /dev/null 2>&1 || fail "add example"
ps stack add "$wk" --dev --yes > /dev/null 2>&1 || fail "add the dev stack"
ps sync installed --record > /dev/null; ps sync baseline > /dev/null
reasons() { ps sync check --json | python3 -c "import json,sys; print(' '.join(sorted(r['kind'] for r in json.load(sys.stdin))))"; }

echo "L1 sync check in the stacks layout"
check "a pinned stack with a newer release in range" bash -c "$(declare -f ps reasons); T='$T' h='$h' H='$H'; reasons | grep -qw stack && ps sync check | grep -q 'example v1.1.0 is out in range'"
(cd "$fws" && echo 9.0.0 > VERSION && git commit -qam "psai 9" && git tag v9.0.0 && git push -q "$T/fw.git" main --tags)
check "a newer framework release" bash -c "$(declare -f ps reasons); T='$T' h='$h' H='$H'; ps sync check | grep -q 'psai v9.0.0 is out'"

echo "L1 targets: one stage and one PR branch per repo you own"
check "psai stage: the overlay's stage worktree" test "$(ps stage)" = "$H/state/stage/nostack"
check "psai stage <dev stack>: that stack's" test "$(ps stage mine)" = "$H/state/stage/mine"
check "a pinned stack is never a target" bash -c "$(declare -f ps); T='$T' h='$h' H='$H'; ! ps stage example"
mkdir -p "$H/state/stage/nostack/guides"; printf '# Mine\n' > "$H/state/stage/nostack/guides/mine.md"
printf '# Notes\n\n- dev stack rule\n' > "$H/state/stage/mine/guides/notes.md"
mkdir -p "$H/overlay/knowledge/example/roles/doer"; printf '# Inbox\n\n## 2026-11-22: a finding\n- Tag: fact\n' > "$H/overlay/knowledge/example/roles/doer/inbox.md"
printf '# Retro: a task\n## Findings\n1. [high] checks: one\n' > "$T/report.md"
out="$(cd "$T" && HOME="$h" PSAI_TRACE="$T/none" python3 "$H/framework/scripts/psai.py" retro finish --report "$T/report.md")"
br="psai/retro-box-$today"
check "retro finish: a branch in your overlay, pushed to its remote" bash -c "git -C '$T/ov.git' rev-parse -q --verify '$br' && git -C '$T/ov.git' show '$br:guides/mine.md' | grep -q Mine && git -C '$T/ov.git' show '$br:knowledge/example/roles/doer/inbox.md' | grep -q 'a finding'"
check "and one in the dev stack's repo, pushed to its remote" bash -c "git -C '$T/mine.git' show '$br:guides/notes.md' | grep -q 'dev stack rule' && ! git -C '$T/mine.git' show '$br:guides/mine.md' 2>/dev/null"
check "each carries the report as its description" bash -c "grep -q '\[high\] checks' '$H/state/prs/nostack-psai-retro-box-$today.md' && grep -q '\[high\] checks' '$H/state/prs/mine-psai-retro-box-$today.md'"
check "the stages are emptied; the live repos weren't switched" bash -c "test ! -e '$H/state/stage/nostack/guides/mine.md' && test ! -e '$H/state/stage/mine/guides/notes.md' && test \"\$(git -C '$H/overlay' rev-parse --abbrev-ref HEAD)\" = main && test \"\$(git -C '$wk' rev-parse --abbrev-ref HEAD)\" = work"
out="$(cd "$T" && HOME="$h" PSAI_TRACE="$T/none" python3 "$H/framework/scripts/psai.py" retro finish --report "$T/report.md")"
check "nothing new: no PR" grep -q 'no PR' <<< "$out"

echo "L1 suggestions for a pinned stack's author"
S="$(ps stage)"; o="$(ps stack override example:guides/example-rules.md --in "$S")"; echo "- the owner's fix" >> "$o"
ps retro suggest example --note "the rules miss a case" > "$T/sug.out" 2>&1
d="$(ls "$H/state/suggestions/example/"*.md 2>/dev/null | head -1)"
check "suggest drafts a note with the diff, and asks before opening anything" bash -c "test -n '$d' && grep -q 'the rules miss a case' '$d' && grep -q '^+- the owner.s fix' '$d' && grep -q 'ask the owner' '$T/sug.out' && test ! -d '$H/state/suggestions/example/repo'"
ps retro suggest example --note "the rules miss a case" --open --local > "$T/sug2.out" 2>&1
check "--open --local: a branch in a clone of the stack, at its pin, with the change" bash -c "r='$H/state/suggestions/example/repo'; b=\$(git -C \$r rev-parse --abbrev-ref HEAD); [[ \$b == psai/suggest-box-* ]] && git -C \$r show HEAD:guides/example-rules.md | grep -q 'the owner.s fix' && test \"\$(git -C \$r rev-parse HEAD~1)\" = \"\$(git -C '$ex' rev-parse v1.0.0)\" && ! git -C '$ex' branch -a | grep -q suggest"

echo "L1 update: your overlay ff-only with the inbox union; the framework refused while a stack doesn't support it"
o2="$T/ov2"; git clone -q "$T/ov.git" "$o2"; (cd "$o2" && git checkout -q main && mkdir -p knowledge && printf '# Inbox\n\n## 2026-11-20: from the other machine\n- Tag: fact\n' > knowledge/inbox.md && git add -A && git commit -qm other && git push -q origin main)
printf '# Inbox\n\n## 2026-11-22: local\n- Tag: fact\n' > "$H/overlay/knowledge/inbox.md"
fw0="$(git -C "$H/framework" rev-parse HEAD)"
out="$(PSAI_EVAL=1 ps update 2>&1)"; rc=$?
check "the overlay fast-forwards, keeping the local inbox entry" bash -c "grep -q 'from the other machine' '$H/overlay/knowledge/inbox.md' && grep -q '2026-11-22: local' '$H/overlay/knowledge/inbox.md'"
check "a framework release outside a stack's psai range is refused (exit 4), nothing moved" bash -c "test $rc = 4 && grep -q 'outside the psai range of: example, mine' <<< \"\$1\" && test \"\$(git -C '$H/framework' rev-parse HEAD)\" = '$fw0'" _ "$out"
PSAI_EVAL=1 ps update --force > "$T/force.out" 2>&1
check "--force takes it and disables those stacks in your overlay" bash -c "test \"\$(cat '$H/framework/VERSION')\" = 9.0.0 && python3 -c \"import yaml,sys; m=yaml.safe_load(open('$H/overlay/stack.yaml')); sys.exit(0 if set(m['disable'])=={'example','mine'} else 1)\""
check "status: one line per stack" bash -c "$(declare -f ps); T='$T' h='$h' H='$H'; o=\"\$(ps status)\"; grep -q '^stack example: 1.0.0 at v1.0.0 (pinned); needs psai' <<< \"\$o\" && grep -q '^stack mine: ' <<< \"\$o\""
exit $((fails > 0))
