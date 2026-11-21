#!/usr/bin/env bash
# L1 tests for `psai publish` (ADR 0011, section 11): check first, refuse a dirty tree or an existing tag, tag and push
# to a local bare remote, and with --standalone build the packages for a release (a fake gh records the call; no
# network). Prints "  ok   ..." / "  FAIL ..." (check.sh runs it).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
FX="$ROOT/evals/fixtures/stacks/example"
[ -d "$FX" ] || exit 0
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
unset PSAI_HOME PSAI_STATE PSAI_TRACE PSAI_ROLE PSAI_EVAL
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
fails=0
pass() { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; fails=$((fails + 1)); }
check() { local msg="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$msg"; else fail "$msg"; fi; }
S="$T/example"; cp -r "$FX" "$S"; printf 'dist/\n' > "$S/.gitignore"
(cd "$S" && git init -q -b main && git add -A && git commit -qm one && git init -q --bare "$T/remote.git" && git remote add origin "$T/remote.git" && git push -q -u origin main)
mkdir -p "$T/bin"; printf '#!/bin/sh\necho "gh $*" >> "%s/gh.log"\necho https://example.invalid/release\n' "$T" > "$T/bin/gh"; chmod +x "$T/bin/gh"
P() { (cd "$S" && HOME="$T" PATH="$T/bin:$PATH" python3 "$ROOT/scripts/psai.py" publish "$@"); }

echo "L1 psai publish"
check "refuses without --yes when it can't ask" bash -c "$(declare -f P); S='$S' T='$T' ROOT='$ROOT'; ! P < /dev/null && ! git -C '$S' rev-parse -q --verify refs/tags/v1.0.0"
echo x >> "$S/README.md"
check "refuses a dirty tree" bash -c "$(declare -f P); S='$S' T='$T' ROOT='$ROOT'; ! P --yes && ! git -C '$S' rev-parse -q --verify refs/tags/v1.0.0"
git -C "$S" checkout -q README.md
sed -i 's|steps/do.md|steps/nope.md|' "$S/workflows/example.yaml"; (cd "$S" && git commit -qam broken)
check "refuses a stack that fails psai check" bash -c "$(declare -f P); S='$S' T='$T' ROOT='$ROOT'; ! P --yes && ! git -C '$S' rev-parse -q --verify refs/tags/v1.0.0"
sed -i 's|steps/nope.md|steps/do.md|' "$S/workflows/example.yaml"; (cd "$S" && git commit -qam fixed)
check "--dry-run says what it would do and changes nothing" bash -c "$(declare -f P); S='$S' T='$T' ROOT='$ROOT'; P --dry-run | grep -q 'tag v1.0.0 at' && ! git -C '$S' rev-parse -q --verify refs/tags/v1.0.0"
P --yes > "$T/pub.out" 2>&1 || { fail "publish"; cat "$T/pub.out"; }
check "tags v<version> and pushes the tag" bash -c "git -C '$S' rev-parse -q --verify refs/tags/v1.0.0 && git -C '$T/remote.git' rev-parse -q --verify refs/tags/v1.0.0"
check "refuses a version that is already tagged" bash -c "$(declare -f P); S='$S' T='$T' ROOT='$ROOT'; ! P --yes"
git -C "$S" tag -d v1.0.0 > /dev/null
out="$(P --yes 2>&1)"; rc=$?
check "refuses a tag the remote already has" bash -c "test $rc != 0 && grep -q 'already has the tag' <<< \"\$1\" && ! git -C '$S' rev-parse -q --verify refs/tags/v1.0.0" _ "$out"
sed -i 's/^version: 1.0.0/version: 1.1.0/' "$S/stack.yaml"; (cd "$S" && git commit -qam "1.1.0")
P --standalone --yes > "$T/pub2.out" 2>&1 || { fail "publish --standalone"; cat "$T/pub2.out"; }
check "--standalone: a GitHub release of the tag with one zip per target" bash -c "grep -q '^gh release create v1.1.0 .*example-1.1.0-claude.zip .*example-1.1.0-opencode.zip' '$T/gh.log' && git -C '$T/remote.git' rev-parse -q --verify refs/tags/v1.1.0"
check "a published release installs with psai stack add" bash -c "mkdir -p '$T/h/.claude' && HOME='$T/h' bash '$ROOT/install.sh' >/dev/null 2>&1 && cd '$T' && HOME='$T/h' python3 '$ROOT/scripts/psai.py' stack add '$T/remote.git' --yes >/dev/null 2>&1 && grep -q 'ref: v1.1.0' '$T/h/.psai/overlay/stacks.yaml'"
exit $((fails > 0))
