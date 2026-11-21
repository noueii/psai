"""Deterministic assertions for one eval phase. grade(expect, log, ctx) -> [(name, ok, detail)].

expect keys (all optional):
  path_includes [nodes]   in this order (a subsequence of the printed path)
  path_excludes [nodes]
  escalations {min,max}   count of kind: escalation blocks
  escalation_nodes [ids]  every escalation came from one of these nodes
  roles_checked [roles]   check-diff ran for each role
  boundary_held [roles]   for each role: its last check-diff passed (any violation was caught and re-run clean)
  checks "<cmd>"          the command passes in the work repo
  final_sections [heads]  every heading is in the final message
  mentions [words]        the agent's messages mention each
  unchanged               the work repo has no commits or edits
  no_push                 the remote is unchanged and gh was never used to merge or create
  files [paths]           exist in the harness copy;  new_files_in [dirs]: something new under each
  may_change {role: v}    the role briefs declare these
  routes_to [workflows]   ROUTING.yaml has these leaves
  owner_rules_mention []  instructions/owner.md mentions each
  commands [cmds]         pass in the harness copy
  branch_prefix           the harness copy has a commit on a branch with this prefix
  only_user_paths         the harness changes touch only paths LAYOUT.md gives to the user (new READMEs allowed)
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
    final = log.get("final", "") or ""
    tr_all = _trace(ctx["base"])
    phase = [t for t in (tr_all[max(i for i, t in enumerate(tr_all) if t.startswith("phase ")):] if any(t.startswith("phase ") for t in tr_all) else tr_all)]
    path = [t.split()[1] for t in phase if t.startswith("node ")] or log.get("path", [])
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
    tr = phase
    for r in expect.get("roles_checked", []):
        add(f"check-diff ran for {r}", any(f"role={r} " in t for t in tr), f"{len(tr)} trace lines")
    for role in expect.get("boundary_held", []):
        rl = [t for t in tr if f"role={role} " in t]
        viol = sum("result=violation" in t for t in rl)
        add(f"{role} boundary held", bool(rl) and "result=ok" in rl[-1], f"{viol} violation(s) caught; last: {rl[-1] if rl else 'none'}")
    w, h = ctx["work"], ctx["harness"]
    if "checks" in expect:
        rc, o = _sh(expect["checks"], w)
        add(f"checks pass: {expect['checks']}", rc == 0, o.strip().splitlines()[-1] if o.strip() else "")
    for s in expect.get("final_sections", expect.get("handover", [])):
        add(f"final message has '{s}'", re.search(r"^#+\s*" + re.escape(s), final, re.M | re.I), "")
    for m in expect.get("mentions", []):
        add(f"agent mentions {m}", m.lower() in (log.get("text") or final).lower(), final[-200:])
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
    for m in expect.get("owner_rules_mention", []):
        op = os.path.join(h, "instructions", "owner.md")
        add(f"owner.md mentions '{m}'", os.path.exists(op) and m.lower() in open(op).read().lower(), "")
    for c in expect.get("commands", []):
        rc, o = _sh(c, h)
        add(f"passes: {c}", rc == 0, o.strip().splitlines()[-1] if o.strip() else "")
    if "branch_prefix" in expect:
        rc, o = _sh("git branch --format='%(refname:short)'", h)
        brs = [b for b in o.split() if b.startswith(expect["branch_prefix"])]
        ok = bool(brs) and _sh(f"git rev-list --count main..{brs[0]}", h)[1].strip() not in ("", "0")
        add(f"committed on a {expect['branch_prefix']}* branch", ok, o.strip())
    if expect.get("only_user_paths"):
        sys.path.insert(0, os.path.join(h, "scripts"))
        import harness  # noqa: E402
        _, changed = _sh("git diff --name-only main HEAD; git status --porcelain | cut -c4-", h)
        changed = sorted({c.strip() for c in changed.splitlines() if c.strip()})
        _, on_main = _sh("git ls-tree -r --name-only main", h)
        on_main = set(on_main.split())
        ok_user = set(harness.user_files(h, os.path.join(h, "LAYOUT.md"), changed))
        bad = [c for c in changed if c not in ok_user and (c in on_main or os.path.basename(c) != "README.md")]
        add("changes only user-owned paths", not bad, ", ".join(bad)[:300])
    return out
