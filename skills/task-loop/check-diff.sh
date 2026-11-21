#!/usr/bin/env bash
# Usage: check-diff.sh <engineer|qa|reviewer> <base-commit>
# Lists what a role changed since <base-commit> (commits, working tree,
# untracked files) and exits 1 if the role went outside its boundary.
# QA_ALLOW (an extended regex) adds repo-specific check paths for QA.
set -euo pipefail

role="${1:?role required}"
base="${2:?base commit required}"

changed="$(
  {
    git diff --name-only "$base"
    git ls-files --others --exclude-standard
  } | sort -u
)"

qa_re='(^|/)(tests?|__tests__|specs?|e2e|testdata|fixtures)/|[._-](test|spec)\.[^/]+$|_test\.go$'
[ -n "${QA_ALLOW:-}" ] && qa_re="$qa_re|$QA_ALLOW"

case "$role" in
  engineer) bad="" ;;
  qa) bad="$(printf '%s\n' "$changed" | grep -Ev "$qa_re" | grep -v '^$' || true)" ;;
  reviewer) bad="$changed" ;;
  *) echo "unknown role: $role" >&2; exit 2 ;;
esac

if [ -n "$bad" ]; then
  echo "BOUNDARY VIOLATION ($role) touched:"
  printf '%s\n' "$bad" | sed 's/^/  /'
  exit 1
fi
echo "ok: $role stayed within bounds ($(printf '%s' "$changed" | grep -c . || true) files changed)"
