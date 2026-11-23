#!/usr/bin/env bash
# Usage: check-diff.sh <role file> <base-commit>
# Reads `may_change: anything|tests|nothing` from the brief's frontmatter, lists what changed since
# <base-commit> (commits, working tree, untracked files) and exits 1 on a violation.
# TESTS_ALLOW (an extended regex) adds repo-specific test or check paths.
# Each check appends one line to $PSAI_TRACE, or <git-dir>/psai-trace (read by trace.sh).
set -euo pipefail

brief="${1:?role brief required}"
base="${2:?base commit required}"
role="$(basename "$brief" .md)"
may="$(awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} /^may_change:/ {sub(/^may_change:[[:space:]]*/, ""); print}' "$brief")"
[ -n "$may" ] || { echo "no may_change in $brief" >&2; exit 2; }

changed="$( { git diff --name-only "$base"; git ls-files --others --exclude-standard; } | sort -u | grep -v '^$' || true)"
tests_re='(^|/)(tests?|__tests__|specs?|e2e|testdata|fixtures)/|[._-](test|spec)\.[^/]+$|_test\.go$|^test_[^/]*\.py$|/test_[^/]*\.py$'
[ -n "${TESTS_ALLOW:-}" ] && tests_re="$tests_re|$TESTS_ALLOW"

case "$may" in
  anything) bad="" ;;
  tests) bad="$(printf '%s\n' "$changed" | grep -Ev "$tests_re" | grep -v '^$' || true)" ;;
  nothing) bad="$changed" ;;
  *) echo "unknown may_change: $may" >&2; exit 2 ;;
esac

n="$(printf '%s' "$changed" | grep -c . || true)"
PSAI_TRACE="${PSAI_TRACE:-$(git rev-parse --absolute-git-dir)/psai-trace}"
if [ -n "$bad" ]; then
  echo "check-diff role=$role may_change=$may result=violation files=$(echo $bad | tr ' ' ',')" >> "$PSAI_TRACE"
  echo "BOUNDARY VIOLATION ($role, may_change: $may) touched:"
  printf '%s\n' "$bad" | sed 's/^/  /'
  exit 1
fi
echo "check-diff role=$role may_change=$may result=ok files=$n" >> "$PSAI_TRACE"
echo "ok: $role stayed within may_change: $may ($n files changed)"
