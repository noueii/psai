#!/usr/bin/env python3
"""psai publish (ADR 0011, section 11): release a stack you author.

  psai publish [<stack>|<path>] [--standalone] [--remote origin] [--yes] [--dry-run]

It runs `psai check` on the stack, refuses a dirty tree or a tag that already exists (locally or on the remote), then
tags `v<version>` (stack.yaml) and pushes the tag. With --standalone it also builds the packages
(`psai build --standalone`), zips one per target and attaches them to a GitHub release of that tag (`gh release
create`). Tagging, pushing and the release are outward-facing: it shows what it will do and asks first (--yes skips;
without a terminal it refuses rather than guess). Users then install the release with `psai stack add <repo>`.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402
import resolve as res  # noqa: E402
import stacks  # noqa: E402


class PublishError(Exception):
    pass


def git(d, *args):
    p = subprocess.run(["git", "-C", d, *args], capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def publish(ref=None, standalone=False, remote="origin", yes=False, dry=False):
    src = build.stack_path(ref)
    meta = res.load_stack(src)
    name, version = meta.get("name"), str(meta.get("version"))
    tag = f"v{version}"
    if git(src, "rev-parse", "--git-dir")[0]:
        raise PublishError(f"{src} isn't a git repo")
    print(f"psai publish: checking {name} {version}")
    if stacks.check_dir(src, name, res.home(), label=name):
        raise PublishError("psai check failed: fix it first")
    if git(src, "status", "--porcelain")[1]:
        raise PublishError("the working tree has uncommitted changes: commit or stash them first")
    if git(src, "rev-parse", "-q", "--verify", f"refs/tags/{tag}")[0] == 0:
        raise PublishError(f"the tag {tag} already exists: bump version in stack.yaml")
    rc, out, err = git(src, "ls-remote", "--tags", remote, f"refs/tags/{tag}")
    if rc:
        raise PublishError(f"can't reach the remote {remote!r}: {err}")
    if out:
        raise PublishError(f"{remote} already has the tag {tag}: bump version in stack.yaml")
    head = git(src, "rev-parse", "--short", "HEAD")[1]
    plan = [f"tag {tag} at {head} in {src}", f"push {tag} to {remote}"]
    if standalone:
        plan.append(f"build the standalone packages and attach them to a GitHub release {tag} (gh release create)")
    print("psai publish: will\n" + "\n".join(f"  - {p}" for p in plan))
    if dry:
        print("psai publish: dry run; nothing changed")
        return 0
    if not yes:
        if not sys.stdin.isatty():
            raise PublishError("not confirmed: pass --yes to publish without asking")
        if input("Publish? [y/N] ").strip().lower() not in ("y", "yes"):
            raise PublishError("not published")
    rc, _, err = git(src, "tag", "-a", tag, "-m", f"{name} {version}")
    if rc:
        raise PublishError(f"git tag failed: {err}")
    rc, _, err = git(src, "push", remote, tag)
    if rc:
        raise PublishError(f"git push {remote} {tag} failed (the tag stays local): {err}")
    print(f"psai publish: {name} {tag} pushed to {remote}")
    if not standalone:
        return 0
    with tempfile.TemporaryDirectory() as t:
        _, built = build.build(src, build.TARGETS, os.path.join(t, "dist"))
        assets = []
        for b in built:
            target = os.path.basename(b)
            assets.append(shutil.make_archive(os.path.join(t, f"{name}-{version}-{target}"), "zip", b))
        if not shutil.which("gh"):
            keep = os.path.join(src, "dist", "release")
            os.makedirs(keep, exist_ok=True)
            for a in assets:
                shutil.copy2(a, keep)
            print(f"psai publish: gh isn't installed; the packages are in {keep}: attach them to the {tag} release yourself")
            return 0
        p = subprocess.run(["gh", "release", "create", tag, *assets, "--title", f"{name} {version}",
                            "--notes", f"{meta.get('description', '')}\n\nInstall: `psai stack add <this repo> --ref {tag}`, "
                                       "or one of the standalone packages below (no psai needed)."],
                           cwd=src, capture_output=True, text=True)
        if p.returncode:
            raise PublishError(f"gh release create failed (the tag is pushed): {p.stderr.strip()}")
        print(f"psai publish: release {p.stdout.strip()} with {len(assets)} package(s)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="psai publish", description=__doc__.split("\n\n")[0])
    ap.add_argument("stack", nargs="?", help="a stack folder or an installed stack (default: this folder)")
    ap.add_argument("--standalone", action="store_true", help="also attach the standalone packages to a GitHub release")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--yes", action="store_true", help="don't ask to confirm")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        return publish(a.stack, a.standalone, a.remote, a.yes, a.dry_run)
    except (PublishError, build.BuildError) as e:
        print(f"psai publish: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
