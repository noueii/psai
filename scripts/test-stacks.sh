#!/usr/bin/env bash
# L1 tests for `psai stack add|remove|update|list|sync|diff` (ADR 0011, section 11): temp HOMEs, local git repos made
# from the fixture stacks, no network, no AI, never the real HOME. Prints "  ok   ..." / "  FAIL ..." (check.sh runs it).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
FIX="$ROOT/evals/fixtures/stacks/example"; FS="$ROOT/evals/fixtures/stacks"
[ -d "$FIX" ] || exit 0
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
unset PSAI_HOME PSAI_STATE PSAI_TRACE PSAI_ROLE PSAI_EVAL XDG_CONFIG_HOME
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
fails=0
pass() { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; fails=$((fails + 1)); }
check() { local msg="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$msg"; else fail "$msg"; fi; }
G() { git -C "$1" "${@:2}" -q; }

# Stack repos. example: v1.0.0, v1.1.0, and v2.0.0 (needs psai >=9: out of range). other: v0.2.0, requires example.
ex="$T/src/example"; mkdir -p "$ex"; cp -r "$FIX"/. "$ex/"
(cd "$ex" && git init -q -b main && git add -A && git commit -qm one && git tag v1.0.0)
echo "- a 1.1 rule" >> "$ex/guides/example-rules.md"; sed -i 's/^version: 1.0.0/version: 1.1.0/' "$ex/stack.yaml"
(cd "$ex" && git commit -qam two && git tag v1.1.0)
sed -i 's/^version: 1.1.0/version: 2.0.0/; s/^psai: .*/psai: ">=9 <10"/' "$ex/stack.yaml"
(cd "$ex" && git commit -qam three && git tag v2.0.0 && git commit -q --allow-empty -m "on main, untagged")
ot="$T/src/other"; mkdir -p "$ot"; cp -r "$FS/other"/. "$ot/"
sed -i "s|source: \"github:noueii/psai-example\"|source: \"$ex\"|" "$ot/stack.yaml"
mkdir -p "$ot/my-skills/change-notes/scripts"; printf '#!/bin/sh\ntouch "$HOME/RAN"\n' > "$ot/my-skills/change-notes/scripts/run.sh"
printf '#!/bin/sh\ntouch "$HOME/RAN"\n' > "$ot/install.sh"
(cd "$ot" && git init -q -b main && git add -A && git commit -qm one && git tag v0.2.0)
nd="$T/src/needy"; mkdir -p "$nd"
printf 'schema: 1\nname: needy\nversion: 0.1.0\ndescription: "Needs a newer example."\npsai: ">=2.1 <4"\nrequires:\n  - { name: example, source: "%s", version: ">=3.0" }\n' "$ex" > "$nd/stack.yaml"
(cd "$nd" && git init -q -b main && git add -A && git commit -qm one && git tag v0.1.0)
bad="$T/src/bad"; mkdir -p "$bad"; printf 'schema: 1\nname: nostack\nversion: 1.0.0\ndescription: "x"\npsai: ">=2.1 <4"\n' > "$bad/stack.yaml"
(cd "$bad" && git init -q -b main && git add -A && git commit -qm one && git tag v1.0.0)

# A home made by install.sh in a temp HOME.
h="$T/h"; mkdir -p "$h/.claude" "$h/.pi/agent"; H="$h/.psai"
HOME="$h" bash "$ROOT/install.sh" > /dev/null 2>&1 || fail "install"
ps() { (cd "$T" && HOME="$h" python3 "$ROOT/scripts/psai.py" "$@"); }
ent() { python3 -c "
import sys, yaml; e = {x['name']: x for x in yaml.safe_load(open('$H/overlay/stacks.yaml'))['stacks']}
sys.exit(0 if ($1) else 1)"; }

echo "L1 psai stack add"
check "refuses a branch as the ref" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps stack add '$ex' --ref main --yes"
check "refuses without --yes when it can't ask" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps stack add '$ex' --ref v1.0.0 < /dev/null"
check "refuses a release whose psai range excludes this framework" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps stack add '$ex' --ref v2.0.0 --yes"
check "refuses a reserved name" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps stack add '$bad' --yes"
check "refuses a requires conflict (one version per stack)" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps stack add '$ex' --ref v1.0.0 --as example --yes && ! ps stack add '$nd' --yes; r=\$?; ps stack remove example >/dev/null; exit \$r"
test -z "$(ls -A "$H/stacks")" && pass "a refused add leaves nothing behind" || fail "a refused add left: $(ls -A "$H/stacks")"
ps stack add "$ex" --yes > "$T/add.out" 2>&1 || { fail "add example"; cat "$T/add.out"; }
check "no --ref: the newest release that takes this psai (v1.1.0, not v2.0.0)" ent "e['example']['ref'] == 'v1.1.0' and e['example']['mode'] == 'pinned' and e['example']['version'] == '1.1.0'"
check "the clone is checked out at the pinned commit" test "$(git -C "$H/stacks/example" rev-parse HEAD)" = "$(git -C "$ex" rev-parse v1.1.0^{commit})"
check "add shows what it injects and exports before installing" bash -c "grep -q 'injected: - example:example: Any task' '$T/add.out' && grep -q 'exports: workflows: example' '$T/add.out'"
check "the stack's skill is linked into the tools" test "$(readlink "$h/.claude/skills/change-notes")" = "$H/stacks/example/my-skills/change-notes"
check "its content resolves by name" test "$(ps resolve role example:doer)" = "$H/stacks/example/roles/doer.md"
check "refuses a second stack with the same name" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps stack add '$ex' --ref v1.0.0 --yes"
ps stack add "$ex" --ref "$(git -C "$ex" rev-parse v1.0.0^{commit})" --as example-old --yes > /dev/null 2>&1
check "--as installs under another name, pinned to a commit" ent "e['example-old']['commit'] == '$(git -C "$ex" rev-parse v1.0.0^{commit})'"
ps stack add "$ot" --yes > "$T/add2.out" 2>&1 || { fail "add other"; cat "$T/add2.out"; }
check "add lists the skill scripts and never runs anything from the stack" bash -c "grep -q 'skill scripts.*my-skills/change-notes/scripts/run.sh' '$T/add2.out' && test ! -e '$h/RAN'"
check "requires already installed in range: used as is" ent "e['other']['version'] == '0.2.0' and e['example']['ref'] == 'v1.1.0'"
check "a skill name two stacks ship: the first is linked, the clash reported" bash -c "test \"\$(readlink '$h/.claude/skills/change-notes')\" = '$H/stacks/example/my-skills/change-notes'"
check "psai route shows both stacks" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; o=\"\$(ps route)\"; grep -q '^- other:triage: ' <<< \"\$o\" && grep -q '^- example:example: ' <<< \"\$o\""
wk="$T/work-clone"; git clone -q "$ex" "$wk"; git -C "$wk" checkout -q -b work v1.1.0
ps stack add "$wk" --dev --as mine-dev --yes > /dev/null 2>&1
check "--dev links your working clone" bash -c "test \"\$(readlink '$H/stacks/mine-dev')\" = '$wk' && python3 -c \"import yaml,sys; e={x['name']:x for x in yaml.safe_load(open('$H/overlay/stacks.yaml'))['stacks']}; sys.exit(0 if e['mine-dev']['mode']=='dev' else 1)\""

echo "L1 psai stack list, update, diff"
ps stack list --json > "$T/list.json"
check "list: name, version, ref, mode, priority, workflows" python3 -c "
import json; r={x['name']: x for x in json.load(open('$T/list.json'))}
assert r['example']['version']=='1.1.0' and r['example']['mode']=='pinned' and r['example']['workflows']==1 and r['example']['priority']==50
assert r['other']['priority']==40 and r['mine-dev']['mode']=='dev'"
ps stack update example-old > "$T/upd.out" 2>&1
check "update moves a pin to the newest release in range" bash -c "grep -q 'example-old: .* -> v1.1.0' '$T/upd.out' && test \"\$(git -C '$H/stacks/example-old' rev-parse HEAD)\" = \"\$(git -C '$ex' rev-parse v1.1.0^{commit})\""
ps stack update example-old --to v1.0.0 > /dev/null 2>&1
check "update --to pins an older release" bash -c "python3 -c \"import yaml,sys; e={x['name']:x for x in yaml.safe_load(open('$H/overlay/stacks.yaml'))['stacks']}; sys.exit(0 if e['example-old']['ref']=='v1.0.0' else 1)\""
check "update --to refuses a release out of range" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps stack update example-old --to v2.0.0"
ps stack diff example-old > "$T/diff.out" 2>&1
check "diff shows the change since the pin" grep -q 'guides/example-rules.md' "$T/diff.out"
(cd "$wk" && echo "- dev change" >> guides/example-rules.md && git commit -qam dev)
check "update leaves a dev stack without upstream alone" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps stack update mine-dev | grep -q 'mine-dev: dev'"

echo "L1 overrides: .base.yaml, drift on update, diff, check with overrides in place"
ps stack update example-old --to v1.0.0 > /dev/null 2>&1
o="$(ps stack override example-old:guides/example-rules.md)"
check "override copies the file into overrides/<stack>/ and resolve finds it" bash -c "test '$o' = '$H/overlay/overrides/example-old/guides/example-rules.md' && test -f '$o' && test \"\$(cd '$T' && HOME='$h' python3 '$ROOT/scripts/psai.py' resolve guide example-old:example-rules)\" = '$o'"
check "override records the stack's commit and the original's hash in .base.yaml" python3 -c "
import yaml; b = yaml.safe_load(open('$H/overlay/overrides/example-old/.base.yaml'))
f = b['files']['guides/example-rules.md']; assert f['commit'] == '$(git -C "$ex" rev-parse v1.0.0^{commit})' and len(f['sha256']) == 64"
echo "- my own rule" >> "$o"
check "override again keeps your edits" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps stack override example-old:guides/example-rules.md >/dev/null && grep -q 'my own rule' '$o'"
check "knowledge, stack.yaml and the framework can't be overridden" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps stack override example-old:knowledge/roles/doer/INDEX.md && ! ps stack override example-old:stack.yaml && ! ps stack override psai:skills/work/SKILL.md"
ps stack update example-old > "$T/upd2.out" 2>&1
check "update reports an original that changed under your override" grep -q 'example-old:guides/example-rules.md changed upstream since you overrode it; diff with `psai stack diff example-old guides/example-rules.md`' "$T/upd2.out"
check "update keeps the override" grep -q 'my own rule' "$o"
check "list counts overrides and warns about changed originals" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps stack list --json | python3 -c \"import json,sys; r={x['name']:x for x in json.load(sys.stdin)}['example-old']; sys.exit(0 if r['overrides']==1 and any('changed upstream' in w for w in r['warnings']) else 1)\""
check "diff <stack> <path> shows the override against its original" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; d=\"\$(ps stack diff example-old guides/example-rules.md)\"; grep -q '^-- a 1.1 rule' <<< \"\$d\" && grep -q '^+- my own rule' <<< \"\$d\""
check "check passes with a valid override in place" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps stack check example-old | grep -q 'ok   example-old: content and refs (1 override(s) in place)'"
w="$(ps stack override example-old:workflows/example.yaml)"
python3 - "$w" <<'PY'
import sys, yaml
p = sys.argv[1]; wf = yaml.safe_load(open(p))
wf["nodes"]["check"]["next"] = [{"when": "changes needed", "to": "do"}, {"when": "done", "to": "report"}]
del wf["nodes"]["approve"]
yaml.safe_dump(wf, open(p, "w"), sort_keys=False)
PY
check "check runs the stack's cases against the overridden workflow (they fail here)" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps stack check example-old"
printf -- '- name: straight through, no approval\n  path: [do, check, report, ready]\n- name: blocked escalates\n  take: { do: [blocked] }\n  path: [do, escalate]\n' > "$(dirname "$w")/example.cases.yaml"
check "the overlay's own cases next to the override are used instead" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps stack check example-old | grep -q 'simulate: 4/4 cases passed'"
python3 -c "import yaml; p='$w'; wf=yaml.safe_load(open(p)); wf['nodes']['report']['next']=[{'to': 'nowhere'}]; yaml.safe_dump(wf, open(p,'w'), sort_keys=False)"
check "check fails on a broken override" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps stack check example-old"
rm -rf "$H/overlay/overrides/example-old/workflows"

echo "L1 skills across stacks: who the tools see, each role's own copy, reserved names, caches, adopt --to"
relink() { HOME="$h" bash "$ROOT/install.sh" --relink > /dev/null 2>&1; }
mks() { mkdir -p "$1"; printf -- '---\nname: %s\ndescription: "%s. Use when testing."\n---\n%s\n' "$(basename "$1")" "${2:-x}" "${2:-x}" > "$1/SKILL.md"; }
check "a name several stacks ship: the higher-priority (then earlier) stack's copy is linked" test "$(readlink "$h/.claude/skills/change-notes")" = "$H/stacks/example/my-skills/change-notes"
mks "$H/overlay/my-skills/change-notes" mine; relink
check "the overlay's copy wins the bare name" test "$(readlink "$h/.claude/skills/change-notes")" = "$H/overlay/my-skills/change-notes"
rm -rf "$H/overlay/my-skills/change-notes"; printf 'priority: {other: 90}\n' >> "$H/overlay/stack.yaml"; relink
check "the overlay's priority: decides between stacks" test "$(readlink "$h/.claude/skills/change-notes")" = "$H/stacks/other/my-skills/change-notes"
check "stack list --skills says which copy the tools see and which aren't linked" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps stack list --skills --json | python3 -c \"import json,sys; r={x['name']:x for x in json.load(sys.stdin)}['change-notes']; sys.exit(0 if r['tools_see']=='other' and 'example' in r['hidden'] else 1)\""
sed -i '/^priority: {other: 90}$/d' "$H/overlay/stack.yaml"; relink
check "a role gets its own stack's copy (other)" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps node other:triage sort | grep -q 'Your skills: change-notes (.*$H/stacks/other/my-skills/change-notes/SKILL.md)'"
check "a role gets its own stack's copy (example)" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps node example:example do | grep -q 'Your skills: change-notes (.*$H/stacks/example/my-skills/change-notes/SKILL.md)'"
check "stack check warns about unprefixed skill names" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps stack check other | grep -q 'warn other: my-skills/change-notes: prefix your skill names (other-change-notes)'"
mks "$wk/my-skills/work" "an impostor"; relink
check "a framework name is reserved: the tools keep psai's, and stack check fails" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; test \"\$(readlink '$h/.claude/skills/work')\" = '$H/framework/skills/work' && ! ps stack check mine-dev"
rm -rf "$wk/my-skills/work"
pkr="$T/src/pk"; mks "$pkr/pk" one; (cd "$pkr" && git init -q -b main && git add -A && git commit -qm one && git tag v1)
mks "$pkr/pk" two; (cd "$pkr" && git commit -qam two && git tag v2)
printf 'skills:\n  - {name: pk, source: "%s", path: pk, ref: v1}\n' "$pkr" > "$H/overlay/skills.yaml"
printf 'skills:\n  - {name: pk, source: "%s", path: pk, ref: v2}\n' "$pkr" > "$wk/skills.yaml"
sed -i 's/required: \[change-notes\]/required: [change-notes, pk]/' "$wk/roles/doer.md"; relink
check "the same skill pinned by two stacks at two refs is fetched twice" bash -c "test \"\$(git -C '$H/state/skills-cache/nostack/pk' rev-parse HEAD)\" = \"\$(git -C '$pkr' rev-parse v1)\" && test \"\$(git -C '$H/state/skills-cache/mine-dev/pk' rev-parse HEAD)\" = \"\$(git -C '$pkr' rev-parse v2)\""
check "the tools see the overlay's pin; the stack's role gets its own" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; test \"\$(readlink '$h/.claude/skills/pk')\" = '$H/state/skills-cache/nostack/pk/pk' && ps node mine-dev:example do | grep -q 'pk (use when testing; $H/state/skills-cache/mine-dev/pk/pk/SKILL.md)'"
mks "$h/.claude/skills/own-x" "an unmanaged skill"
check "adopt --to refuses a pinned stack" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps adopt own-x --to example && test -d '$h/.claude/skills/own-x' -a ! -L '$h/.claude/skills/own-x'"
ps adopt own-x --to mine-dev > /dev/null 2>&1
check "adopt --to a dev stack moves it into that stack's my-skills/ and links it" bash -c "test -f '$wk/my-skills/own-x/SKILL.md' && test \"\$(readlink '$h/.claude/skills/own-x')\" = '$H/stacks/mine-dev/my-skills/own-x'"
check "the registry has a stack column" bash -c "cd '$T' && HOME='$h' python3 '$ROOT/scripts/harness.py' skills --root '$H' | grep -E '^own-x +mine-dev '"

echo "L1 psai new-stack, check, eval"
ps new-stack acme --dir "$T/acme" --description "Acme's review workflows." > "$T/new.out" 2>&1 || { fail "new-stack"; cat "$T/new.out"; }
check "new-stack copies the template and fills stack.yaml" bash -c "grep -q '^name: acme' '$T/acme/stack.yaml' && grep -q \"Acme's review workflows\" '$T/acme/stack.yaml' && ! grep -rq '__NAME__\|__PSAI__' '$T/acme' && test -f '$T/acme/.github/workflows/psai.yml'"
check "new-stack's psai range is this major" bash -c "grep -q \"^psai: \\\">=\$(cut -d. -f1 < '$ROOT/VERSION').0 <\$((\$(cut -d. -f1 < '$ROOT/VERSION') + 1))\\\"\" '$T/acme/stack.yaml'"
check "new-stack makes a git repo and adds it as a dev stack" bash -c "git -C '$T/acme' rev-parse HEAD && test \"\$(readlink '$H/stacks/acme')\" = '$T/acme' && grep -q 'name: acme' '$H/overlay/stacks.yaml'"
check "a new stack passes psai check, by name and by path" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps check acme && ps check '$T/acme'"
check "new-stack refuses a reserved name" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps new-stack nostack --dir '$T/x'"
mkdir -p "$T/acme/workflows"; printf 'name: review\nwhen: Reviews.\nstart: a\nnodes:\n  a: {step: steps/nope.md, next: [{to: done}]}\n  done: {terminal: true}\n' > "$T/acme/workflows/review.yaml"
check "psai check fails on a broken stack" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps check acme"
check "psai check with no argument checks every installed stack" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; o=\"\$(ps check)\"; grep -q 'ok   nostack: content and refs' <<< \"\$o\" && grep -q 'FAIL acme' <<< \"\$o\""
rm "$T/acme/workflows/review.yaml"
printf 'name: acme-smoke\nlevel: L3\nfixture: textkit\ntask: Say hello.\nowner: { max_turns: 1 }\nexpect: {}\n' > "$T/acme/evals/scenarios/smoke.yaml"
e="$(cd "$T" && HOME="$h" python3 "$ROOT/scripts/psai.py" eval acme --prepare-only 2>/dev/null | tail -1)"
check "psai eval builds a temp home with the stack installed (and runs no agent here)" bash -c "test -f '$e/stacks/acme/stack.yaml' && test -f '$e/overlay/stack.yaml' && grep -q 'name: acme' '$e/overlay/stacks.yaml' && test \"\$(readlink '$e/framework')\" != ''"
ps stack remove acme > /dev/null 2>&1

echo "L1 psai stack remove, sync"
check "remove refuses a stack another one requires" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ! ps stack remove example"
mkdir -p "$H/overlay/overrides/other/guides"; echo "# mine" > "$H/overlay/overrides/other/guides/private.md"
ps stack remove other > "$T/rm.out" 2>&1
check "remove deletes the clone, keeps your overrides and says so" bash -c "test ! -e '$H/stacks/other' && test -f '$H/overlay/overrides/other/guides/private.md' && grep -q 'kept your 1 override' '$T/rm.out'"
ps stack remove mine-dev > /dev/null 2>&1
check "remove unlinks a dev stack, never deletes your clone" bash -c "test ! -e '$H/stacks/mine-dev' && test -d '$wk/.git'"
check "remove unlinks its skills when no other stack ships them" bash -c "$(declare -f ps); T='$T' h='$h' ROOT='$ROOT'; ps stack remove example-old && ps stack remove example && test ! -L '$h/.claude/skills/change-notes'"
ps stack add "$ex" --ref v1.0.0 --yes > /dev/null 2>&1; ps stack add "$ot" --yes > /dev/null 2>&1
h2="$T/h2"; mkdir -p "$h2/.claude"; HOME="$h2" bash "$ROOT/install.sh" > /dev/null 2>&1
cp "$H/overlay/stacks.yaml" "$h2/.psai/overlay/stacks.yaml"
(cd "$T" && HOME="$h2" python3 "$ROOT/scripts/psai.py" stack sync) > "$T/sync.out" 2>&1
check "sync installs stacks.yaml's stacks on a new machine, at the recorded commits" bash -c "test \"\$(git -C '$h2/.psai/stacks/example' rev-parse HEAD)\" = \"\$(git -C '$ex' rev-parse v1.0.0^{commit})\" && test -f '$h2/.psai/stacks/other/workflows/triage.yaml' && test -L '$h2/.claude/skills/change-notes'"
before="$(cd "$h2" && find . | sort | md5sum)"; (cd "$T" && HOME="$h2" python3 "$ROOT/scripts/psai.py" stack sync) > /dev/null 2>&1
check "sync again changes nothing" test "$before" = "$(cd "$h2" && find . | sort | md5sum)"
h3="$T/h3"; mkdir -p "$h3/.claude"; HOME="$h3" bash "$ROOT/install.sh" > /dev/null 2>&1
(cd "$T" && HOME="$h3" python3 "$ROOT/scripts/psai.py" stack add "$ot" --yes) > "$T/req.out" 2>&1
check "requires not installed: installed with it, the newest release in its range" bash -c "grep -q 'other requires example' '$T/req.out' && python3 -c \"import yaml,sys; e={x['name']:x for x in yaml.safe_load(open('$h3/.psai/overlay/stacks.yaml'))['stacks']}; sys.exit(0 if e['example']['ref']=='v1.1.0' and 'other' in e else 1)\""
HOME="$h" bash "$ROOT/install.sh" --uninstall > /dev/null 2>&1
check "uninstall keeps the stacks" test -f "$H/stacks/example/stack.yaml" -a -f "$H/overlay/stacks.yaml"
exit $((fails > 0))
