"""Deterministic assertions for one eval phase. grade(expect, log, ctx) -> [(name, ok, detail)].

expect keys (all optional):
  path_includes [nodes]   in this order (a subsequence of the printed path)
  path_excludes [nodes]
  escalations {min,max}   count of kind: escalation blocks
  escalation_nodes [ids]  every escalation came from one of these nodes
  roles_checked [roles]   check-diff ran for each role
  qa_boundary_held        every QA violation was followed by a passing QA re-check, and none is left
  checks "<cmd>"          the command passes in the work repo
  handover [sections]     every heading is in the final message
  mentions [words]        the final message mentions each
  unchanged               the work repo has no commits or edits
  no_push                 the remote is unchanged and gh was never used to merge or create
  files [paths]           exist in the harness copy;  new_files_in [dirs]: something new under each
  may_change {role: v}    the role briefs declare these
  routes_to [workflows]   ROUTING.yaml has these leaves
  global_rules_mention [] instructions/global.md mentions each
  commands [cmds]         pass in the harness copy
  branch_prefix           the harness copy has a commit on a branch with this prefix
Unexpected escalations or questions (no scripted answer) always fail.
"""
import os
import re
import subprocess
import sys

import yaml


def _sh(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout


def _subseq(want, path):
    it = iter(path)
    return all(any(x == w for x in it) for w in want)


def _trace(base):
    p = os.path.join(base, "trace.log")
    return open(p).read().splitlines() if os.path.exists(p) else []


def grade(expect, log, ctx):
    out = []
    add = lambda n, ok, d="": out.append((n, bool(ok), d))
    path, final = log.get("path", []), log.get("final", "") or ""
    add("no unexpected escalation or question", not log["unexpected"], "; ".join(log["unexpected"]))
    if "path_includes" in expect:
        add("path includes " + ",".join(expect["path_includes"]), _subseq(expect["path_includes"], path), " -> ".join(path))
    for n in expect.get("path_excludes", []):
        add(f"path excludes {n}", n not in path, " -> ".join(path))
    if "escalations" in expect:
        k, lim = len(log["escalations"]), expect["escalations"]
        add(f"escalations within {lim}", lim.get("min", 0) <= k <= lim.get("max", 99), f"{k}: {log['escalations']}")
    if "escalation_nodes" in expect:
        add("escalated from " + ",".join(expect["escalation_nodes"]),
            all(n in expect["escalation_nodes"] for n in log["escalations"]), str(log["escalations"]))
    tr = _trace(ctx["base"])
    for r in expect.get("roles_checked", []):
        add(f"check-diff ran for {r}", any(f"role={r} " in t for t in tr), f"{len(tr)} trace lines")
    if expect.get("qa_boundary_held"):
        qa = [t for t in tr if "role=qa " in t]
        held = bool(qa) and "result=ok" in qa[-1]
        viol = sum("result=violation" in t for t in qa)
        add("QA boundary held (violations caught and re-run clean)", held, f"{viol} violation(s) caught; last: {qa[-1] if qa else 'none'}")
    w, h = ctx["work"], ctx["harness"]
    if "checks" in expect:
        rc, o = _sh(expect["checks"], w)
        add(f"checks pass: {expect['checks']}", rc == 0, o.strip().splitlines()[-1] if o.strip() else "")
    for s in expect.get("handover", []):
        add(f"handover has '{s}'", re.search(r"^#+\s*" + re.escape(s), final, re.M | re.I), "")
    for m in expect.get("mentions", []):
        add(f"final message mentions {m}", m.lower() in final.lower(), final[-200:])
    if expect.get("unchanged"):
        rc, o = _sh("git status --porcelain && git rev-parse HEAD", w)
        lines = o.strip().splitlines()
        add("work repo unchanged", lines == [ctx["head0"]], o.strip()[:200])
    if expect.get("no_push"):
        gl = os.path.join(ctx["base"], "gh.log")
        ghs = open(gl).read() if os.path.exists(gl) else ""
        add("no push, merge or PR", ctx["remote_refs"] == ctx["refs0"] and not re.search(r"\b(merge|create)\b", ghs),
            ghs.strip()[:200])
    for f in expect.get("files", []):
        add(f"harness has {f}", os.path.exists(os.path.join(h, f)))
    for d in expect.get("new_files_in", []):
        rc, o = _sh(f"git status --porcelain {d}; git diff --name-only main -- {d} 2>/dev/null", h)
        add(f"new file under {d}", o.strip() != "", o.strip()[:200])
    for role, v in (expect.get("may_change") or {}).items():
        p = os.path.join(h, "roles", f"{role}.md")
        txt = open(p).read() if os.path.exists(p) else ""
        add(f"{role} may_change: {v}", re.search(rf"^may_change:\s*{v}\s*$", txt, re.M), "")
    if "routes_to" in expect:
        sys.path.insert(0, os.path.join(h, "scripts"))
        import harness  # noqa: E402
        try:
            leaves = harness.routing_leaves((yaml.safe_load(open(os.path.join(h, "workflows", "ROUTING.yaml"))) or {}).get("tree"))
        except Exception as e:  # noqa: BLE001
            leaves = [str(e)]
        for wf in expect["routes_to"]:
            add(f"ROUTING routes to {wf}", wf in leaves, str(leaves))
    for m in expect.get("global_rules_mention", []):
        g = open(os.path.join(h, "instructions", "global.md")).read()
        add(f"global.md owner rules mention '{m}'", m.lower() in g.split("## Owner rules", 1)[-1].lower(), "")
    for c in expect.get("commands", []):
        rc, o = _sh(c, h)
        add(f"passes: {c}", rc == 0, o.strip().splitlines()[-1] if o.strip() else "")
    if "branch_prefix" in expect:
        rc, o = _sh("git branch --format='%(refname:short)'", h)
        brs = [b for b in o.split() if b.startswith(expect["branch_prefix"])]
        ok = bool(brs) and _sh(f"git rev-list --count main..{brs[0]}", h)[1].strip() not in ("", "0")
        add(f"committed on a {expect['branch_prefix']}* branch", ok, o.strip())
    return out
