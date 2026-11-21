#!/usr/bin/env python3
"""Retro support for the retro skill (`psai retro ...`).

  gather [--session ID]   print the facts of the run: the ledger record, the workflow trace (path, loops that hit
                          their limit, check-diff rejections, escalations, unused nodes), the inbox entries added
                          this session, what's staged, always-loaded file sizes, time and tokens.
  finish --report FILE    save the report, mark the session's retro done, then build one PR per target repo with
                          everything from the task (`sync.build_prs(kind=retro)`: your overlay, each dev stack you
                          touched), unless the running workflow still has a sync node ahead: then sync builds them.
  suggest <stack> [--note TEXT] [--open [--local]]
                          a pinned stack's flaw (ADR 0011, section 7): draft a suggestion for its author from your
                          overlay's overrides of it (state/suggestions/<stack>/<date>.md, with the diff). --open, only
                          after the owner said yes, builds a branch in a clone of the stack with the change and, unless
                          --local, forks the repo and opens the PR to its author with gh.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import harness  # noqa: E402
import ledger  # noqa: E402
import sync  # noqa: E402


def trace_path():
    if os.environ.get("PSAI_TRACE"):
        return os.environ["PSAI_TRACE"]
    p = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], capture_output=True, text=True)
    return os.path.join(p.stdout.strip(), "psai-trace") if p.returncode == 0 else ""


def current_run(path=None):
    """(workflow name, [trace lines of its latest run])."""
    path = path or trace_path()
    try:
        lines = open(path).read().splitlines()
    except OSError:
        return None, []
    starts = [i for i, line in enumerate(lines) if line.startswith("workflow ")]
    if not starts:
        return None, []
    return lines[starts[-1]].split()[1], lines[starts[-1] + 1:]


def workflow(root, name):
    import resolve  # noqa: PLC0415
    try:
        return yaml.safe_load(open(resolve.resolve("workflow", name, h=resolve.home(root)))) or {}
    except (resolve.ResolveError, OSError):
        return {}


def analyse(wf, run):
    nodes = wf.get("nodes") or {}
    path = [line.split()[1] for line in run if line.startswith("node ")]
    exh = (wf.get("defaults") or {}).get("on_exhaust")
    limits, prev = [], None
    for n in path:
        if prev and n == exh and n not in {e.get("to") for e in (nodes.get(prev) or {}).get("next") or []}:
            limits.append(prev)
        prev = n
    rejected = [line for line in run if line.startswith("check-diff ") and "result=violation" in line]
    escal = [n for n in path if "return" in (nodes.get(n) or {})]
    unused = [n for n in nodes if n not in path and not any(k in (nodes[n] or {}) for k in harness.SPECIAL)]
    return {"path": path, "limits_hit": limits, "rejections": rejected, "escalations": escal, "unused": unused}


def sync_ahead(root):
    """True when the latest workflow run sits at a retro node that has a sync node ahead of it."""
    name, run = current_run()
    if not name:
        return False
    wf = workflow(root, name)
    nodes = wf.get("nodes") or {}
    path = [line.split()[1] for line in run if line.startswith("node ")]
    if not path or (nodes.get(path[-1]) or {}).get("terminal"):
        return False
    seen, todo = set(), [e.get("to") for e in (nodes.get(path[-1]) or {}).get("next") or []]
    while todo:
        x = todo.pop()
        if x in seen or x not in nodes:
            continue
        seen.add(x)
        if (nodes[x] or {}).get("skill") == "sync":
            return True
        todo += [e.get("to") for e in (nodes[x] or {}).get("next") or []]
    return False


def new_entries(root, rec):
    base = (rec or {}).get("inbox_at_start") or {}
    out = []
    for f in ledger.inbox_files(root):
        rel = os.path.relpath(f, root)
        text = sync.read(f) or ""
        ents = [e.strip() for e in re.split(r"(?m)^(?=## )", text) if e.startswith("## ")]
        for e in ents[base.get(rel, 0):]:
            out.append(f"[{rel}]\n{e}")
    return out


def tokens(transcript):
    tot = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    try:
        for line in open(transcript):
            try:
                u = ((json.loads(line).get("message") or {}).get("usage")) or {}
            except ValueError:
                continue
            tot["input"] += u.get("input_tokens", 0) or 0
            tot["output"] += u.get("output_tokens", 0) or 0
            tot["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
            tot["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
    except OSError:
        return None
    return tot


def words(path):
    t = sync.read(path)
    return len(t.split()) if t else 0


def gather(root, sid=None):
    root = sync.root_of(root)
    rec = ledger.current(root, sid)
    out = ["# Run facts for the retro", ""]
    if rec:
        start = datetime.datetime.fromisoformat(rec["start"])
        mins = (datetime.datetime.now().astimezone() - start).total_seconds() / 60
        out += [f"- session {rec['id']} ({rec.get('tool')}), project {rec.get('project')}, psai {rec.get('psai_version')}",
                f"- started {rec['start']} ({mins:.0f} min ago); workflows: {', '.join(rec.get('workflows') or []) or 'none'}; "
                f"escalations: {rec.get('escalations', 0)}"]
        tk = tokens(rec["transcript"]) if rec.get("transcript") else None
        if tk:
            out.append(f"- tokens so far: {tk['input']} in, {tk['output']} out, {tk['cache_read']} cache read, "
                       f"{tk['cache_write']} cache write")
    else:
        out.append("- no ledger record for this session (the plugin isn't installed here?)")
    pend = [r["id"] for r in ledger.pending_retro(root)]
    if pend:
        out.append(f"- earlier sessions that ended without a retro: {', '.join(pend)} (finish with --pending to cover them)")
    name, run = current_run()
    out += ["", "## Workflow trace"]
    if name:
        a = analyse(workflow(root, name), run)
        out += [f"- {name}: {' -> '.join(a['path'])}",
                f"- loops that hit their limit (went to on_exhaust from): {', '.join(a['limits_hit']) or 'none'}",
                f"- check-diff rejections: {len(a['rejections'])}"] + [f"  - {r}" for r in a["rejections"]] + [
                f"- escalations entered: {len(a['escalations'])}",
                f"- nodes never visited: {', '.join(a['unused']) or 'none'}"]
    else:
        out.append("- no workflow ran in this repo")
    ents = new_entries(root, rec)
    out += ["", f"## Inbox entries added this session ({len(ents)})"] + (ents or ["- none"])
    pend = sync.all_pending(root)
    _, skipped = sync.pending_changes(root)
    out += ["", f"## Staged or captured, not yet in a PR ({sum(len(c) for c in pend.values())})"]
    for n, ch in pend.items():
        out += [f"- [{n}] {p}" + (" (deleted)" if s is None else "") for p, s in sorted(ch.items())]
    h = ledger.home(root)
    if not h.compat:
        out += ["", "## Where findings go (targets)", "- your overlay (nostack): your preferences, environment, knowledge"]
        out += [f"- {s.name}: {'dev: you author it; stage in `psai stage ' + s.name + '`' if s.mode == 'dev' else 'pinned: an override in your overlay, plus a suggestion for its author (`psai retro suggest ' + s.name + '`)'}"
                for s in h.stacks]
    if skipped:
        out.append(f"- upstream-owned files edited locally (never PR'd from here): {', '.join(skipped)}")
    proj = (rec or {}).get("project") or ledger.project_of(None)
    loaded = [("instructions/global.md", os.path.join(sync.framework_of(root), "instructions", "global.md")),
              ("instructions/owner.md", os.path.join(root, "instructions", "owner.md"))]
    loaded += [(os.path.relpath(p, proj), p) for p in (os.path.join(proj, n) for n in ("CLAUDE.md", "AGENTS.md")) if os.path.exists(p)]
    nudge = len(harness.context(root).split())
    out += ["", "## Always-loaded text", f"- the psai nudge: {nudge} words"] + [f"- {n}: {words(p)} words" for n, p in loaded if os.path.exists(p)]
    return "\n".join(out) + "\n"


def finish(root, report, sid=None, pending=False, local=False):
    root = sync.root_of(root)
    rec = ledger.current(root, sid)
    os.makedirs(sync.st(root, "reports"), exist_ok=True)
    name = f"{datetime.datetime.now():%Y%m%d-%H%M%S}-{ledger.path_id((rec or {}).get('id', 'session'))}.md"
    dst = sync.st(root, "reports", name)
    shutil.copyfile(report, dst)
    if rec:
        ledger.update(rec["id"], root, retro=True)
    if pending:
        for r in ledger.pending_retro(root):
            ledger.update(r["id"], root, retro=True)
    if sync_ahead(root):
        print("psai retro: report saved; a sync node follows in this workflow, so sync builds the PRs and carries it")
        return 0
    res = sync.build_prs(root, "retro", "", title=None, local=local)
    sync._print_pr(res, "retro")
    return 0


def suggest(root, stack, note="", do_open=False, local=False):
    """Draft (and, when asked, open) a suggestion for a pinned stack's author from the overlay's overrides of it, in
    the live overlay or in its stage worktree."""
    import resolve  # noqa: PLC0415
    import stacks  # noqa: PLC0415
    root = sync.root_of(root)
    h = ledger.home(root)
    st = h.get(stack)
    if st is None or stack in resolve.RESERVED:
        print(f"psai retro suggest: no installed stack {stack}", file=sys.stderr)
        return 3
    srcs = {}
    for base in (h.overlay_path, sync.stage_dir(root, "nostack")):
        d = os.path.join(base, "overrides", stack)
        for dp, _, fs in os.walk(d):
            for f in fs:
                p = os.path.relpath(os.path.join(dp, f), d)
                if f != ".base.yaml" and not (p.endswith(".cases.yaml") and not os.path.exists(os.path.join(st.path, p))):
                    srcs[p] = os.path.join(dp, f)  # the stage wins over the live overlay
    if not srcs:
        print(f"psai retro suggest: your overlay has no override of {stack}; stage one first (`psai stack override`)",
              file=sys.stderr)
        return 1
    diff = []
    for p, src in sorted(srcs.items()):
        orig = os.path.join(st.path, p)
        r = subprocess.run(["diff", "-u", "--label", f"a/{p}", "--label", f"b/{p}",
                            orig if os.path.exists(orig) else "/dev/null", src], capture_output=True, text=True)
        diff.append(r.stdout)
    author = (st.meta.get("author") or {}).get("github") or "?"
    out = sync.st(root, "suggestions", stack, f"{datetime.datetime.now():%Y%m%d-%H%M%S}.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    e = next((x for x in stacks.entries(h) if x.get("name") == stack), {})
    text = [f"# Suggestion for {stack} ({st.meta.get('repository') or e.get('source', '')}, pinned at {e.get('ref')})",
            f"For: @{author} (stack.yaml author.github). From psai's retro; nothing was sent.", "",
            note.strip() or "(no note)", "", "```diff", "".join(diff).rstrip(), "```"]
    open(out, "w").write("\n".join(text) + "\n")
    print(f"psai retro suggest: drafted {out}")
    if not do_open:
        print("  it stays a draft: ask the owner (the fixed block, kind question) before opening a PR to the author "
              f"(`psai retro suggest {stack} --open`)")
        return 0
    src_url = stacks.source_url(e.get("source") or st.meta.get("repository") or "")
    repo = sync.st(root, "suggestions", stack, "repo")
    if not os.path.isdir(os.path.join(repo, ".git")):
        if subprocess.run(["git", "clone", "-q", src_url, repo], capture_output=True).returncode:
            print(f"psai retro suggest: can't clone {src_url}", file=sys.stderr)
            return 1
    branch = f"psai/suggest-{sync.host()}-{datetime.datetime.now():%Y%m%d-%H%M%S}"
    sync.g(repo, "fetch", "-q", "origin")
    sync.g(repo, "checkout", "-q", "-b", branch, e.get("commit") or "HEAD")
    for p, src in srcs.items():
        os.makedirs(os.path.dirname(os.path.join(repo, p)) or repo, exist_ok=True)
        shutil.copyfile(src, os.path.join(repo, p))
    sync.g(repo, "add", "-A")
    sync.g(repo, *sync._ident(repo), "commit", "-q", "-m", f"Suggestion from a psai user: {note.strip()[:60] or stack}")
    print(f"psai retro suggest: branch {branch} in {repo}")
    if local or not shutil.which("gh"):
        print("  local only: push it to your fork of the stack and open the PR to its author yourself")
        return 0
    gh = sync.gh_repo(repo)
    if not gh:
        print("  the stack isn't on GitHub: send the draft to its author instead")
        return 0
    subprocess.run(["gh", "repo", "fork", gh, "--remote", "--remote-name", "fork", "--clone=false"], cwd=repo,
                   capture_output=True)
    if sync.g(repo, "push", "-q", "-u", "fork", branch, timeout=60)[0]:
        print("  push to your fork failed; the branch stays local", file=sys.stderr)
        return 1
    login = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True).stdout.strip()
    p = subprocess.run(["gh", "pr", "create", "--repo", gh, "--head", f"{login}:{branch}" if login else branch,
                        "--title", f"Suggestion: {note.strip()[:60] or stack}", "--body-file", out],
                       capture_output=True, text=True, cwd=repo)
    print(f"  PR: {p.stdout.strip()}" if p.returncode == 0 else f"  gh pr create failed: {p.stderr.strip()}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="psai retro")
    ap.add_argument("cmd", choices=["gather", "finish", "suggest"])
    ap.add_argument("stack", nargs="?", help="suggest: the pinned stack")
    ap.add_argument("--note", default="", help="suggest: why, for the author")
    ap.add_argument("--open", action="store_true", help="suggest: build the branch and open the PR (only after a yes)")
    ap.add_argument("--root", default=None)
    ap.add_argument("--session", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--pending", action="store_true", help="finish: also cover earlier sessions waiting for a retro")
    ap.add_argument("--local", action="store_true", help="finish: build the branch but don't push it")
    a = ap.parse_args(argv)
    if a.cmd == "gather":
        sys.stdout.write(gather(a.root, a.session))
        return 0
    if a.cmd == "suggest":
        if not a.stack:
            ap.error("suggest takes the stack's name")
        return suggest(a.root, a.stack, a.note, a.open, a.local)
    if not a.report or not os.path.exists(a.report):
        ap.error("finish needs --report <file>")
    return finish(a.root, a.report, a.session, a.pending, a.local)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
