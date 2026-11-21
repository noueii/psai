#!/usr/bin/env python3
"""Retro support for the retro skill (`psai retro ...`).

  gather [--session ID]   print the facts of the run: the ledger record, the workflow trace (path, loops that hit
                          their limit, check-diff rejections, escalations, unused nodes), the inbox entries added
                          this session, what's staged, always-loaded file sizes, time and tokens.
  finish --report FILE    save the report, mark the session's retro done, then build the ONE PR with everything from
                          the task (`sync.build_pr(kind=retro)`), unless the running workflow still has a sync node
                          ahead: then sync builds the PR and carries this report.
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
    proj = ledger.project_of(None)
    for p in (os.path.join(proj, ".psai", "workflows", f"{name}.yaml"), os.path.join(root, "workflows", f"{name}.yaml")):
        if os.path.exists(p):
            return yaml.safe_load(open(p)) or {}
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
    ch, skipped = sync.pending_changes(root)
    out += ["", f"## Staged or captured, not yet in a PR ({len(ch)})"] + [f"- {p}" + (" (deleted)" if s is None else "")
                                                                         for p, s in sorted(ch.items())]
    if skipped:
        out.append(f"- upstream-owned files edited locally (never PR'd from here): {', '.join(skipped)}")
    proj = (rec or {}).get("project") or ledger.project_of(None)
    loaded = [("instructions/global.md", os.path.join(root, "instructions", "global.md")),
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
        print("psai retro: report saved; a sync node follows in this workflow, so sync builds the one PR and carries it")
        return 0
    res = sync.build_pr(root, "retro", "", title=None, local=local)
    sync._print_pr(res, "retro")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="psai retro")
    ap.add_argument("cmd", choices=["gather", "finish"])
    ap.add_argument("--root", default=None)
    ap.add_argument("--session", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--pending", action="store_true", help="finish: also cover earlier sessions waiting for a retro")
    ap.add_argument("--local", action="store_true", help="finish: build the branch but don't push it")
    a = ap.parse_args(argv)
    if a.cmd == "gather":
        sys.stdout.write(gather(a.root, a.session))
        return 0
    if not a.report or not os.path.exists(a.report):
        ap.error("finish needs --report <file>")
    return finish(a.root, a.report, a.session, a.pending, a.local)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
