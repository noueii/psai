#!/usr/bin/env bash
# Prove, with no AI and no network, the sync and retro machinery: the out-of-sync check against crafted states, the
# ff-only update and its conflict handling, migrations running once, the session ledger written by each plugin's
# hooks, and the one PR branch built against a bare local git remote. Temp HOMEs only.
# Usage: scripts/test-sync.sh   (prints "ok"/"FAIL" lines; exits 1 on any failure; run by check.sh)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
FIX="$ROOT/evals/fixtures/harness-content"
TAIL="$ROOT/evals/fixtures/sync-tail"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
unset PSAI_HOME PSAI_STATE PSAI_TRACE PSAI_ROLE PSAI_EVAL XDG_CONFIG_HOME
export PSAI_HOST=box GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
fails=0
res() { if [ "$2" = 0 ]; then echo "  ok   $1"; else echo "  FAIL $1"; fails=$((fails + 1)); fi; }
check() { local msg="$1"; shift; "$@" >/dev/null 2>&1; res "$msg" $?; }
today="$(date +%Y%m%d)"

# A user's fork: src (with the test content and the sync-tail overlay) -> bare origin -> the live clone at $L.
# HOME=$HM is a temp home with tool folders; the live clone's state is $L/.state.
src="$T/src"; mkdir -p "$src"
(cd "$ROOT" && git ls-files -co --exclude-standard -z | xargs -0 cp --parents -t "$src")
if [ -d "$FIX" ]; then cp -r "$FIX"/workflows "$FIX"/steps "$FIX"/roles "$FIX"/guides "$FIX"/templates "$FIX"/knowledge "$FIX"/my-skills "$src/"; cp -r "$TAIL"/workflows "$TAIL"/steps "$src/"; fi
(cd "$src" && git init -q -b main && git add -A && git commit -qm fork) || res "fork repo" 1
fresh() { # name -> sets L (live clone), HM (home), O (bare origin); recorded as installed, migrated, baselined
  O="$T/$1.git"; L="$T/$1"; HM="$T/$1-home"
  git clone -q --bare "$src" "$O"; git clone -q "$O" "$L"
  mkdir -p "$HM/.claude/skills" "$HM/.agents/skills" "$HM/.pi/agent" "$HM/.omp/agent" "$HM/.config/opencode"
  ln -s "$L" "$HM/.psai"   # as install.sh links it
  ps sync installed --record >/dev/null; ps sync migrate >/dev/null; ps sync baseline >/dev/null
}
ps() { (cd "$L" && HOME="$HM" PSAI_HOME="$L" python3 "$L/scripts/psai.py" "$@"); }
push_up() { # a new commit on origin: file, line
  rm -rf "$T/other"; git clone -q "$O" "$T/other"
  (cd "$T/other" && mkdir -p "$(dirname "$1")" && printf '%s\n' "$2" >> "$1" && git add -A && git commit -qm "upstream: $1" && git push -q origin main)
}
reasons() { ps sync check --no-fetch --json | python3 -c "import json,sys; print(' '.join(sorted(r['kind'] for r in json.load(sys.stdin))))"; }
snapl() { (cd "$L" && git rev-parse HEAD; git status --porcelain; git branch -a; git -C "$O" for-each-ref; find "$HM" -type f -o -type l | sort) | md5sum; }

echo "L1 psai command"
fresh cmd
check "psai --help lists every subcommand" bash -c "o=\"\$(cd '$L' && python3 scripts/psai.py --help)\"; for c in install update status sync retro adopt doctor check context graph simulate; do grep -qw \"\$c\" <<< \"\$o\" || exit 1; done"
check "psai status runs" bash -c "$(declare -f ps); L='$L' HM='$HM'; ps status | grep -q '^install: matches HEAD'"
check "psai doctor shows each present tool" bash -c "$(declare -f ps); L='$L' HM='$HM'; o=\"\$(ps doctor)\"; for t in claude opencode pi omp; do grep -q \"^\$t: \" <<< \"\$o\" || exit 1; done; grep -q 'plugin: NOT LOADED' <<< \"\$o\""
check "psai context and simulate run" bash -c "$(declare -f ps); L='$L' HM='$HM'; ps context | grep -q request-router && ps simulate | grep -q 'cases passed'"

echo "L1 migrations run once per machine"
fresh mig
printf '#!/usr/bin/env bash\n[ "$DRY_RUN" = 1 ] && { echo would: count; exit 0; }\necho run >> "$HOME/count"\n' > "$L/migrations/0002-test-count.sh"
ps sync migrate --dry-run >/dev/null
check "dry-run runs nothing" test ! -e "$HM/count"
ps sync migrate >/dev/null; ps sync migrate >/dev/null
check "a new migration runs once" test "$(cat "$HM/count")" = run
printf '#!/usr/bin/env bash\necho x >> "$HOME/fails"; exit 3\n' > "$L/migrations/0003-test-fail.sh"
ps sync migrate >/dev/null 2>&1; rc=$?; ps sync migrate >/dev/null 2>&1
check "a failing migration exits non-zero and runs again next time" test "$rc" != 0 -a "$(wc -l < "$HM/fails")" = 2
check "pending migrations are out of sync" bash -c "$(declare -f ps reasons); L='$L' HM='$HM'; reasons | grep -qw migrations"
mkdir -p "$HM/old" && ln -s "$L" "$HM/.harness"; rm -f "$L/.state/migrations.json" "$L/migrations/0002-test-count.sh" "$L/migrations/0003-test-fail.sh"
ps sync migrate >/dev/null
check "0001 removes the old ~/.harness link to a psai clone" test ! -L "$HM/.harness"
ln -s "$HM/old" "$HM/.harness"; rm -f "$L/.state/migrations.json"; ps sync migrate >/dev/null
check "0001 leaves a ~/.harness link to anything else" test -L "$HM/.harness"

echo "L1 sync check against crafted states (no fetch, no network)"
fresh chk
before="$(snapl)"
out="$(ps sync check)"; rc=$?
check "nothing to do: in sync, exit 0" bash -c "test $rc = 0 && grep -q 'psai: in sync' <<< '$out'"
out="$(ps sync)"
check "nothing to do: sync is a no-op (no branch, no push, no file)" bash -c "grep -q 'in sync; nothing to do' <<< '$out' && test '$before' = '$(snapl)'"
push_up README.md "upstream change"; (cd "$L" && git fetch -q)
check "behind: a new commit on the fork" bash -c "$(declare -f ps reasons); L='$L' HM='$HM'; reasons | grep -qw behind"
fresh chk2
python3 -c "import json; p='$L/.state/installed.json'; d=json.load(open(p)); d['commit']='0'*40; json.dump(d, open(p,'w'))"
check "install drift: the installed commit isn't HEAD" bash -c "$(declare -f ps reasons); L='$L' HM='$HM'; test \"\$(reasons)\" = install"
ps sync installed --record >/dev/null; rm -f "$L/.state/installed.json"; ps sync installed --record >/dev/null
mkdir -p "$L/.state/sessions"
printf '{"id":"s1","tool":"claude","start":"2026-11-21T10:00:00+00:00","end":"2026-11-21T11:00:00+00:00","captured":{"inbox":2,"staged":0}}\n' > "$L/.state/sessions/s1.json"
check "unsynced: a session captured items not yet in a PR" bash -c "$(declare -f ps reasons); L='$L' HM='$HM'; test \"\$(reasons)\" = unsynced"
rm -f "$L/.state/sessions/s1.json"
printf '# Inbox\n\n## 2026-11-21: a finding\n- Tag: fact\n' > "$L/knowledge/inbox.md"
check "staged: a captured inbox entry not yet in a PR" bash -c "$(declare -f ps reasons); L='$L' HM='$HM'; test \"\$(reasons)\" = staged"
rm -f "$L/knowledge/inbox.md"
mkdir -p "$HM/.claude/skills/new-one"; printf -- '---\nname: new-one\ndescription: "x. Use when x."\n---\n' > "$HM/.claude/skills/new-one/SKILL.md"
check "drift: a new skill in a tool folder" bash -c "$(declare -f ps reasons); L='$L' HM='$HM'; test \"\$(reasons)\" = drift && ps sync drift | grep -q '+new-one'"
ps sync baseline >/dev/null
printf '@~/.psai/instructions/global.md\n' > "$HM/.claude/CLAUDE.md"
check "no drift from psai's own lines in an instruction file" bash -c "$(declare -f ps reasons); L='$L' HM='$HM'; test -z \"\$(reasons)\""
printf 'Always answer in English.\n' >> "$HM/.claude/CLAUDE.md"
check "drift: a user line in a global instruction file" bash -c "$(declare -f ps reasons); L='$L' HM='$HM'; ps sync drift | grep -q 'instructions ~/.claude/CLAUDE.md'"
ps sync baseline >/dev/null
mkdir -p "$HM/.claude/projects/p1/memory"; echo fact > "$HM/.claude/projects/p1/memory/a.md"
check "drift: a new Claude memory file" bash -c "$(declare -f ps reasons); L='$L' HM='$HM'; ps sync drift | grep -q 'memory ~/.claude/projects/p1/memory: +a.md'"
ps sync baseline >/dev/null
up="$T/upstream.git"; git clone -q --bare "$src" "$up"; (cd "$L" && git remote add upstream "$up")
O_SAVE="$O"; O="$up"; push_up LAYOUT.md "<!-- upstream -->"; O="$O_SAVE"; (cd "$L" && git fetch -q upstream)
check "an upstream remote is never merged any more (ADR 0011): no reason to sync" bash -c "$(declare -f ps reasons); L='$L' HM='$HM'; test -z \"\$(reasons)\""

echo "L1 update: fast-forward only, keeps local inbox entries, a conflict changes nothing"
fresh upd
printf '# Inbox\n\n## 2026-11-21: local entry\n- Tag: fact\n' > "$L/knowledge/inbox.md"
printf '\n## 2026-11-21: local role entry\n- Tag: fact\n' >> "$L/knowledge/roles/doer/inbox.md"
push_up knowledge/roles/doer/inbox.md "## 2026-11-20: merged entry"
push_up README.md "upstream readme"
(cd "$L" && git fetch -q)
PSAI_EVAL=1 ps sync update > "$T/upd.out" 2>&1; rc=$?
check "ff-only update moves HEAD to origin/main" bash -c "test $rc = 0 && test \"\$(git -C '$L' rev-parse HEAD)\" = \"\$(git -C '$L' rev-parse origin/main)\""
check "an untouched local inbox entry is kept" grep -q 'local entry' "$L/knowledge/inbox.md"
check "a touched inbox keeps both the merged and the local entries" bash -c "grep -q 'merged entry' '$L/knowledge/roles/doer/inbox.md' && grep -q 'local role entry' '$L/knowledge/roles/doer/inbox.md'"
check "an eval run never re-installs" grep -q 'install.sh skipped' "$T/upd.out"
fresh conf
echo "- local rule" > "$L/instructions/owner.md"
push_up instructions/owner.md "- upstream rule"; (cd "$L" && git fetch -q)
head0="$(git -C "$L" rev-parse HEAD)"
out="$(PSAI_EVAL=1 ps sync update 2>&1)"; rc=$?
check "conflict: exit 4 and 'psai update waiting: needs you'" bash -c "test $rc = 4 && grep -q 'psai update waiting: needs you' <<< '$out'"
check "conflict: nothing changed" bash -c "test \"\$(git -C '$L' rev-parse HEAD)\" = '$head0' && test \"\$(cat '$L/instructions/owner.md')\" = '- local rule'"
fresh div
(cd "$L" && echo local >> README.md && git commit -qam "local commit")
push_up LAYOUT.md "remote"; (cd "$L" && git fetch -q)
head0="$(git -C "$L" rev-parse HEAD)"
out="$(PSAI_EVAL=1 ps sync --no-fetch 2>&1)"; rc=$?
check "diverged: sync reports it, exits 4 and changes nothing" bash -c "test $rc = 4 && grep -q 'needs you' <<< '$out' && test \"\$(git -C '$L' rev-parse HEAD)\" = '$head0'"

echo "L1 the session ledger, written by each plugin's hooks (temp HOME)"
fresh led
hk() { (cd "$L" && HOME="$HM" "$@"); }
hk bash -c "echo '{\"session_id\":\"c-1\",\"cwd\":\"$L\",\"transcript_path\":\"/nope\"}' | bash '$L/plugins/claude/hooks/session-start.sh' SessionStart" >/dev/null
q() { python3 -c "import json,sys; r=json.load(open('$L/.state/sessions/$1.json')); sys.exit(0 if ($2) else 1)"; }
check "claude SessionStart opens a record" q c-1 "r['tool']=='claude' and r['project']=='$L' and not r.get('end') and r['psai_version'].startswith('2.')"
hk bash -c "echo '{\"session_id\":\"c-sub\"}' | bash '$L/plugins/claude/hooks/session-start.sh' SubagentStart" >/dev/null
hk bash -c "echo '{\"session_id\":\"c-role\"}' | PSAI_ROLE=doer bash '$L/plugins/claude/hooks/session-start.sh' SessionStart" >/dev/null
check "a subagent or role session opens no record" test ! -e "$L/.state/sessions/c-sub.json" -a ! -e "$L/.state/sessions/c-role.json"
c="$L/.git/psai-trace"
hk bash -c "cd '$L' && PSAI_HOME='$L' skills/work/trace.sh example do" >/dev/null
echo "check-diff role=doer may_change=anything result=ok files=1" >> "$c"
hk bash -c "cd '$L' && PSAI_HOME='$L' skills/work/trace.sh example escalate" >/dev/null
check "trace.sh adds the workflow and the escalation" q c-1 "r['workflows']==['example'] and r['escalations']==1"
printf '\n## 2026-11-21: captured\n- Tag: fact\n' >> "$L/knowledge/inbox.md"
hk bash -c "echo '{\"session_id\":\"c-1\"}' | bash '$L/plugins/claude/hooks/session-end.sh'"
check "claude SessionEnd closes it: captured count, retro pending" q c-1 "r['end'] and r['captured']['inbox']==1 and r['retro_pending'] is True"
check "the next nudge asks for the missed retro" bash -c "cd '$L' && HOME='$HM' python3 scripts/harness.py context '$L' | grep -q '1 earlier session(s) ended without a retro'"
check "psai ledger list shows it" bash -c "$(declare -f ps); L='$L' HM='$HM'; ps ledger list --pending | grep -q '^c-1 .*retro=pending'"
if command -v node >/dev/null; then
  cat > "$T/hooks.mjs" <<'JS'
const [, , root, cwd] = process.argv;
const ctx = (id, kind) => ({ cwd, agent: { kind }, sessionManager: { getSessionId: () => id } });
for (const [tool, id, kind] of [["pi", "pi-1"], ["omp", "omp-1", "main"], ["omp", "omp-sub", "sub"]]) {
  const h = {}; (await import(`${root}/plugins/${tool}/psai.ts`)).default({ on: (e, f) => (h[e] = f) });
  await h.session_start({}, ctx(id, kind)); await h.session_shutdown({}, ctx(id, kind));
}
const { Psai } = await import(`${root}/plugins/opencode/psai.js`);
const hooks = await Psai({ client: { session: { get: async () => ({ data: {} }) } } });
await hooks.event({ event: { type: "session.created", properties: { info: { id: "oc-1", directory: cwd } } } });
await hooks.event({ event: { type: "session.created", properties: { info: { id: "oc-child", parentID: "oc-1", directory: cwd } } } });
await hooks.event({ event: { type: "session.deleted", properties: { info: { id: "oc-1" } } } });
JS
  (cd "$L" && HOME="$HM" PSAI_HOME="$L" node "$T/hooks.mjs" "$L" "$L" 2>/dev/null)
  for x in pi-1:pi omp-1:omp oc-1:opencode; do
    check "${x#*:} plugin opens and closes a record" q "${x%%:*}" "r['tool']=='${x#*:}' and r['end'] and r['project']=='$L'"
  done
  check "omp subagents and opencode child sessions open none" test ! -e "$L/.state/sessions/omp-sub.json" -a ! -e "$L/.state/sessions/oc-child.json"
else echo "  skip node not installed (pi, omp, opencode ledger hooks)"; fi

echo "L1 one PR branch per run, built in a separate worktree (bare local remote, no network)"
fresh pr
S="$(ps sync stage)"
check "the stage is a worktree outside the live tree's status" bash -c "test -e '$S/.git' && test -z \"\$(git -C '$L' status --porcelain)\""
printf -- '# Notes rule\n\nKeep notes short.\n' > "$S/guides/notes.md"
printf '# Inbox\n\n## 2026-11-21: captured\n- Tag: fact\n' > "$L/knowledge/inbox.md"
echo "local edit" >> "$L/README.md"
mkdir -p "$L/.state/reports"; printf '# Retro: a task\n## Findings\n1. [high] checks: a finding\n' > "$L/.state/reports/r1.md"
mkdir -p "$L/.state/sessions"; printf '{"id":"s2","tool":"claude","start":"x","end":"y","captured":{"inbox":1,"staged":1}}\n' > "$L/.state/sessions/s2.json"
echo "Sync summary." > "$T/body.md"
head0="$(git -C "$L" rev-parse HEAD)"
out="$(ps sync pr --body-file "$T/body.md")"
br="psai/sync-box-$today"
check "exactly one psai/ branch, locally and on the fork" bash -c "test \"\$(git -C '$L' branch --list 'psai/*' | wc -l)\" = 1 && git -C '$L' rev-parse -q --verify '$br' && test \"\$(git -C '$O' branch --list 'psai/*' | tr -d ' ')\" = '$br'"
check "it carries the staged guide and the inbox entry" bash -c "git -C '$L' show '$br:guides/notes.md' | grep -q 'Keep notes short' && git -C '$L' show '$br:knowledge/inbox.md' | grep -q captured"
check "it never carries an upstream-owned file edited locally" bash -c "! git -C '$L' diff --name-only '$head0' '$br' | grep -q README.md && grep -q 'Not included' '$L/.state/prs/nostack-psai-sync-box-$today.md'"
check "the description has the summary and the retro report" bash -c "grep -q 'Sync summary' '$L/.state/prs/nostack-psai-sync-box-$today.md' && grep -q '\[high\] checks' '$L/.state/prs/nostack-psai-sync-box-$today.md'"
check "the live clone was not switched or committed" bash -c "test \"\$(git -C '$L' rev-parse HEAD)\" = '$head0' && test \"\$(git -C '$L' rev-parse --abbrev-ref HEAD)\" = main"
check "the stage is emptied, the session marked synced, the report used" bash -c "test ! -e '$S/guides/notes.md' && grep -q '\"synced\": \"$br\"' '$L/.state/sessions/s2.json' && test ! -e '$L/.state/reports/r1.md'"
out="$(ps sync pr --body-file "$T/body.md")"
check "a second run with nothing new: no PR, no branch" bash -c "grep -q 'nothing worth changing: no PR' <<< '$out' && test \"\$(git -C '$L' branch --list 'psai/*' | wc -l)\" = 1"
check "after the PR, the check has nothing staged or unsynced" bash -c "$(declare -f ps reasons); L='$L' HM='$HM'; ! reasons | grep -qwE 'staged|unsynced|reports'"

echo "L1 retro: gather, and finish builds one branch unless a sync node follows"
fresh ret
hk bash -c "echo '{\"session_id\":\"r-1\",\"cwd\":\"$L\"}' | bash '$L/plugins/claude/hooks/session-start.sh' SessionStart" >/dev/null
printf 'workflow example\nnode do\ncheck-diff role=doer may_change=anything result=ok files=1\nnode check\ncheck-diff role=checker may_change=nothing result=violation files=a\ncheck-diff role=checker may_change=nothing result=ok files=0\nnode do\ncheck-diff role=doer may_change=anything result=ok files=1\nnode check\ncheck-diff role=checker may_change=nothing result=ok files=0\nnode do\ncheck-diff role=doer may_change=anything result=ok files=1\nnode check\ncheck-diff role=checker may_change=nothing result=ok files=0\nnode escalate\n' > "$T/trace1"
printf '\n## 2026-11-21: learned\n- Tag: proposed-rule\n' >> "$L/knowledge/inbox.md"
out="$(cd "$L" && HOME="$HM" PSAI_HOME="$L" PSAI_TRACE="$T/trace1" python3 scripts/psai.py retro gather)"
check "gather: the loop that hit its limit, the rejection, the new inbox entry" bash -c "grep -q 'went to on_exhaust from): check' <<< \"\$1\" && grep -q 'check-diff rejections: 1' <<< \"\$1\" && grep -q 'Inbox entries added this session (1)' <<< \"\$1\" && grep -q 'nodes never visited: approve, report, retro, sync' <<< \"\$1\"" _ "$out"
printf 'workflow example\nnode do\nnode check\nnode approve\nnode report\nnode retro\n' > "$T/trace2"
printf '# Retro: a task\n## Findings\n1. [medium] knowledge: keep it\n' > "$T/report.md"
out="$(cd "$L" && HOME="$HM" PSAI_HOME="$L" PSAI_TRACE="$T/trace2" python3 scripts/psai.py retro finish --report "$T/report.md")"
check "at a retro node with sync ahead: no branch, the report waits for sync" bash -c "grep -q 'sync builds the PRs' <<< \"\$1\" && test -z \"\$(git -C '$L' branch --list 'psai/*')\" && ls '$L/.state/reports/' | grep -q '.md$'" _ "$out"
check "the retro is marked done in the ledger" q r-1 "r['retro'] is True"
(cd "$L" && HOME="$HM" PSAI_HOME="$L" python3 scripts/psai.py sync pr >/dev/null)
check "then sync's one branch carries the retro report" bash -c "test \"\$(git -C '$L' branch --list 'psai/*' | tr -d ' ')\" = 'psai/sync-box-$today' && grep -q 'keep it' '$L/.state/prs/nostack-psai-sync-box-$today.md'"
fresh ret2
printf '\n## 2026-11-21: learned\n- Tag: fact\n' >> "$L/knowledge/inbox.md"
printf 'workflow example\nnode do\nnode check\nnode approve\nnode report\nnode ready\n' > "$T/trace3"
out="$(cd "$L" && HOME="$HM" PSAI_HOME="$L" PSAI_TRACE="$T/trace3" python3 scripts/psai.py retro finish --report "$T/report.md" --local)"
check "after a workflow without a sync node: one psai/retro- branch, the report as its description" bash -c "test \"\$(git -C '$L' branch --list 'psai/*' | tr -d ' ')\" = 'psai/retro-box-$today' && grep -q 'keep it' '$L/.state/prs/nostack-psai-retro-box-$today.md' && test -z \"\$(git -C '$O' branch --list 'psai/*')\"" _ "$out"
fresh ret3
out="$(cd "$L" && HOME="$HM" PSAI_HOME="$L" PSAI_TRACE="$T/trace3" python3 scripts/psai.py retro finish --report "$T/report.md")"
check "nothing staged or captured: no PR" bash -c "grep -q 'no PR' <<< \"\$1\" && test -z \"\$(git -C '$L' branch --list 'psai/*')\"" _ "$out"

exit $((fails > 0))
