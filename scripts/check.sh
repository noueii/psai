#!/usr/bin/env bash
# Maintainer checks for psai (and, with a path, for a stack). Dev-only: never shipped to users. Never touches the
# real HOME: every install test runs in a temp HOME.
# Usage: scripts/check.sh [--upstream] [<stack repo>]
#   --upstream    psai itself ships no content (run it before every commit to psai)
#   <stack repo>  check a stack instead of psai (its CI does this)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
UPSTREAM=""; TARGET="$ROOT"
for a in "$@"; do case "$a" in --upstream) UPSTREAM=--upstream ;; *) TARGET="$(cd "$a" && pwd -P)" ;; esac; done
fails=0
pass() { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; fails=$((fails + 1)); }
check() { local msg="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$msg"; else fail "$msg"; fi; }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

python3 "$ROOT/scripts/check.py" "$TARGET" $UPSTREAM || fails=$((fails + 1))

if [ "$TARGET" = "$ROOT" ]; then
  echo "scripts in skills"
  for s in "$ROOT"/skills/*/*.sh "$ROOT"/scripts/*.sh; do check "$(basename "$s") parses" bash -n "$s"; done
  echo "link-skills.sh (temp HOME)"
  h="$T/home"; mkdir -p "$h/.agents/skills/work"
  HOME="$h" "$ROOT/scripts/link-skills.sh" >/dev/null 2>&1
  check "links every skill into ~/.claude/skills" test "$(find "$h/.claude/skills" -maxdepth 1 -type l | wc -l)" = "$(ls -d "$ROOT"/skills/*/ | wc -l)"
  check "leaves a folder that isn't its own alone" test -d "$h/.agents/skills/work" -a ! -L "$h/.agents/skills/work"
  HOME="$h" "$ROOT/scripts/link-skills.sh" >/dev/null 2>&1
  check "is idempotent" test "$(find "$h/.claude/skills" -maxdepth 1 -type l | wc -l)" = "$(ls -d "$ROOT"/skills/*/ | wc -l)"
  HOME="$h" "$ROOT/scripts/link-skills.sh" --unlink >/dev/null 2>&1
  check "--unlink removes only its own links" test -z "$(find "$h/.claude/skills" "$h/.agents/skills" -maxdepth 1 -type l)" -a -d "$h/.agents/skills/work"

  echo "check-diff.sh (temp repo)"
  r="$T/repo"; mkdir -p "$r" && cd "$r" && git init -q && git -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
  printf -- '---\nmay_change: tests\n---\n' > "$T/checker.md"; printf -- '---\nmay_change: nothing\n---\n' > "$T/reviewer.md"
  base="$(git rev-parse HEAD)"; mkdir -p tests && echo x > tests/test_a.py
  check "may_change: tests allows tests/" bash "$ROOT/skills/work/check-diff.sh" "$T/checker.md" "$base"
  echo x > app.py
  check "may_change: tests refuses app.py" bash -c "! bash '$ROOT/skills/work/check-diff.sh' '$T/checker.md' '$base'"
  check "may_change: nothing refuses any change" bash -c "! bash '$ROOT/skills/work/check-diff.sh' '$T/reviewer.md' '$base'"
  cd "$ROOT" || exit 1
fi

if command -v claude >/dev/null; then
  echo "claude plugin validate"
  check "claude plugin validate passes" claude plugin validate "$TARGET"
fi

echo
if [ "$fails" = 0 ]; then echo "check: all passed"; else echo "check: $fails failed"; exit 1; fi
