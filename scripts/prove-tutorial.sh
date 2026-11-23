#!/usr/bin/env bash
# Maintainer-only: the consumer-install proof. Runs every ```sh block of docs/guide/tutorial.md, in order and as
# written, in a temp HOME, then checks that each tool lists the skills (no model session), and what each tool's
# hook or extension adds to a request, against a fake model. No AI runs at any point.
# - psai is served from this clone's HEAD, and the tutorial's stack from an empty repo, both over smart HTTP on
#   localhost (scripts/git-http.py), so `claude plugin marketplace add`, `pi install`, `omp plugin install` and
#   `npx skills add` install from git URLs the way they do from GitHub;
# - a fake model (scripts/fake-model.py) records each tool's requests: no credentials, no real model;
# - the real HOME is never touched. npx needs the network once to fetch the `skills` package.
# Usage: scripts/prove-tutorial.sh [--keep]
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
T="$(mktemp -d)"; KEEP=0; [ "${1:-}" = --keep ] && KEEP=1
GP=18765; MP=18766
cleanup() { kill "${PIDS[@]}" 2>/dev/null; [ "$KEEP" = 1 ] && echo "kept: $T" || rm -rf "$T"; }
PIDS=(); trap cleanup EXIT
fails=0; pass() { echo "  ok   $*"; }; fail() { echo "  FAIL $*"; fails=$((fails + 1)); }

echo "setup: temp HOME, local git server, fake model"
export HOME="$T/home" XDG_CONFIG_HOME="$T/home/.config" XDG_DATA_HOME="$T/home/.local/share" \
  XDG_CACHE_HOME="$T/home/.cache" XDG_STATE_HOME="$T/home/.local/state"
unset PSAI_STACK PSAI_TRACE PI_CODING_AGENT_DIR ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN
export GIT_AUTHOR_NAME=you GIT_AUTHOR_EMAIL=you@example.com GIT_COMMITTER_NAME=you GIT_COMMITTER_EMAIL=you@example.com
mkdir -p "$HOME/.pi/agent" "$HOME/.omp/agent" "$XDG_CONFIG_HOME/opencode" "$T/srv/noueii" "$T/srv/you" "$T/requests"
for port in $GP $MP; do
  python3 -c "import socket,sys; s=socket.socket(); sys.exit(s.connect_ex(('127.0.0.1', $port)) == 0)" || { fail "port $port is in use"; exit 1; }
done
git clone -q --bare "$ROOT" "$T/srv/noueii/psai.git"
git init -q --bare -b main "$T/srv/you/acme.git" && git -C "$T/srv/you/acme.git" config http.receivepack true   # anonymous push, localhost only
python3 "$ROOT/scripts/git-http.py" "$T/srv" --port $GP & PIDS+=($!)
python3 "$ROOT/scripts/fake-model.py" "$T/requests" --port $MP & PIDS+=($!)
sleep 1
export PSAI_GIT="http://127.0.0.1:$GP/noueii/psai.git" ACME_GIT="http://127.0.0.1:$GP/you/acme.git"
git ls-remote "$PSAI_GIT" HEAD >/dev/null && pass "psai is served at $PSAI_GIT" || { fail "git server"; exit 1; }

echo "the tutorial, block by block"
mkdir -p "$T/work" && cd "$T/work" || exit 1
awk '/^```sh$/{on=1; n++; print "echo \"  -- block " n "\""; next} /^```/{on=0; next} on' "$ROOT/docs/guide/tutorial.md" > "$T/tutorial.sh"
if bash -euo pipefail "$T/tutorial.sh" > "$T/tutorial.log" 2>&1; then
  pass "all $(grep -c '^```sh$' "$ROOT/docs/guide/tutorial.md") blocks ran ($T/tutorial.log)"
else
  fail "a tutorial block failed:"; tail -15 "$T/tutorial.log" | sed 's/^/         /'; exit 1
fi
S="$HOME/psai-stack"
git -C "$T/srv/you/acme.git" rev-parse -q --verify refs/tags/v0.2.0 >/dev/null && pass "the stack is pushed, with tags v0.1.0 and v0.2.0" || fail "the stack wasn't pushed"
"$HOME/src/psai/scripts/check.sh" "$S" > "$T/check.log" 2>&1 && pass "the stack passes psai's checks" || fail "the stack fails psai's checks ($T/check.log)"

WANT="request-router work customize-harness capture-knowledge retro sync workflow-acme-change acme-shared acme-rules acme-changelog"
echo "skill discovery, without any model session"
listed() { # <tool> <listing>: every wanted skill appears exactly once
  local tool="$1" out="$2" bad=""
  for s in $WANT; do [ "$(printf '%s' "$out" | grep -cE "(^|[^a-z-])$s([^a-z-]|$)")" -ge 1 ] || bad="$bad $s"; done
  [ -z "$bad" ] && pass "$tool lists psai's and acme's skills" || fail "$tool doesn't list:$bad"
}
cd "$T/work" || exit 1
listed "Claude Code (plugin details)" "$(claude plugin details psai@psai 2>&1; claude plugin details acme@acme 2>&1)"
listed "pi (rpc get_commands, offline)" "$(echo '{"type":"get_commands"}' | timeout 60 pi --mode rpc --no-session --offline 2>/dev/null | grep -o '"skill:[^"]*"' | sort -u)"
listed "omp (rpc get_state)" "$( (echo '{"type":"get_state"}'; sleep 12) | ANTHROPIC_API_KEY=dummy timeout 60 omp --mode rpc --no-session --no-title 2>/dev/null | grep -o '"skill:[^"]*"' | sort -u)"
listed "opencode (debug skill)" "$(timeout 120 opencode debug skill --pure 2>/dev/null | grep '"name"')"

echo "what each tool sends to a model: a load test of the hook and extensions against a fake model (no AI)"
cat > "$HOME/.pi/agent/models.json" <<EOF
{ "providers": { "fake": { "baseUrl": "http://127.0.0.1:$MP/v1", "api": "openai-completions", "apiKey": "dummy",
  "compat": { "supportsDeveloperRole": false, "supportsReasoningEffort": false }, "models": [{ "id": "fake-1" }] } } }
EOF
cat > "$HOME/.omp/agent/models.yml" <<EOF
providers:
  fake: { baseUrl: "http://127.0.0.1:$MP/v1", api: openai-completions, apiKey: dummy,
          compat: { supportsDeveloperRole: false, supportsReasoningEffort: false }, models: [{ id: fake-1 }] }
EOF
python3 - "$XDG_CONFIG_HOME/opencode/opencode.json" "$MP" <<'PY'
import json, sys
p, port = sys.argv[1], sys.argv[2]
c = json.load(open(p))
c["provider"] = {"fake": {"npm": "@ai-sdk/openai-compatible", "name": "fake", "models": {"fake-1": {}},
                          "options": {"baseURL": f"http://127.0.0.1:{port}/v1", "apiKey": "dummy"}}}
json.dump(c, open(p, "w"))
PY
ask() { # <tool> <command...>: run one prompt, then check the newest request the tool sent
  local tool="$1"; shift
  local before; before="$(ls "$T/requests" | wc -l)"
  (cd "$T/work" && timeout 180 "$@" < /dev/null > "$T/$tool.out" 2>&1)
  local req; req="$(python3 - "$T/requests" "$before" <<'PY'
import json, os, sys
d, n = sys.argv[1], int(sys.argv[2])
new = sorted((int(f[:-5]) for f in os.listdir(d)), reverse=True)
new = [f for f in new if f > n]
# the request carrying the system prompt with tools/skills (tools may also send short title requests)
best = max(new, key=lambda f: os.path.getsize(f"{d}/{f}.json"), default=None)
print(f"{d}/{best}.json" if best else "")
PY
)"
  [ -n "$req" ] || { fail "$tool: no request reached the model ($T/$tool.out)"; return; }
  grep -q '# psai' "$req" && pass "$tool: the nudge is in the request" || fail "$tool: no nudge in $req"
  local miss=""; for s in $WANT; do grep -q "$s" "$req" || miss="$miss $s"; done
  [ -z "$miss" ] && pass "$tool: psai's skills and acme's skills are offered" || fail "$tool: missing skills:$miss"
}
ANTHROPIC_BASE_URL="http://127.0.0.1:$MP" ANTHROPIC_API_KEY=dummy ask claude claude -p hello --model claude-sonnet-4-5
ask pi pi -p --no-session --model fake/fake-1 hello
ask omp omp -p --no-session --model fake/fake-1 hello
ask opencode opencode run --pure -m fake/fake-1 hello
before="$(ls "$T/requests" | wc -l)"
(cd "$T/work" && PSAI_ROLE=tester timeout 120 pi -p --no-session --model fake/fake-1 hello < /dev/null > /dev/null 2>&1)
last="$T/requests/$(ls "$T/requests" | sort -n | tail -1)"
[ "$(ls "$T/requests" | wc -l)" -gt "$before" ] && ! grep -q '# psai' "$last" && pass "pi: a role agent (PSAI_ROLE) gets no nudge" || fail "pi: role agent"

echo "the update reached each channel (tutorial step 8)"
grep -rqs 'Name tests after the behaviour' "$HOME/.claude/plugins" && pass "Claude Code has acme 0.2.0" || fail "Claude Code didn't update acme"
grep -rqs 'Name tests after the behaviour' "$HOME/.pi/agent/git" && pass "pi has acme 0.2.0" || fail "pi didn't update acme"
grep -rqs 'Name tests after the behaviour' "$HOME/.omp" && pass "omp has acme 0.2.0" || fail "omp didn't update acme"
grep -qs 'Name tests after the behaviour' "$HOME/.agents/skills/acme-shared/guides/testing.md" && pass "npx skills has acme 0.2.0" || fail "npx skills didn't update acme"

echo
if [ "$fails" = 0 ]; then echo "prove-tutorial: all passed"; else echo "prove-tutorial: $fails failed"; exit 1; fi
