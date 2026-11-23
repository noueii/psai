"""Deterministic assertions for one eval phase. grade(expect, log, ctx) -> [(name, ok, detail)].

expect keys (all optional). "own" is the owner's stack (PSAI_STACK) after the phase (and after `merge: true`):
  path_includes [nodes]   in this order (a subsequence of the traced path)
  path_excludes [nodes]
  ends_terminal           the path ends at a terminal node of any workflow in the run
  escalations {min,max}   count of kind: escalation blocks
  escalation_nodes [ids]  every escalation came from one of these nodes
  roles_checked [roles]   check-diff ran for each role
  boundary_held [roles]   for each role: its last check-diff passed (any violation was caught and re-run clean)
  checks "<cmd>"          the command passes in the work repo
  final_sections [heads]  every heading is in the final message
  mentions [words]        the agent's messages mention each
  answer_mentions [words] the final message mentions each (case-insensitive)
  unchanged               the work repo has no commits or edits
  work_files [paths]      exist in the work repo
  no_push                 the remote is unchanged and gh was never used to merge or create
  own_exists              the owner's stack exists (customize-harness scaffolded it)
  files [globs]           match a file in own;  new_files_in [dirs]: own has something new under each (staged or merged)
  workflow_named <word>   own has a workflow skill skills/workflow-*<word>* with a workflow.yaml
  may_change {role: v}    a role file skills/*/roles/<role>.md in own declares it
  rules_mention [words]   a skills/*-rules/SKILL.md in own mentions each
  own_checks              own passes psai's scripts/check.py
  staged                  something is staged for the owner (the stage worktree, or a psai/ branch) and no other branch
  branches {prefix: n}    own has exactly n local branches starting with each prefix (psai/stage excluded)
  retro_findings          the final message has a Retro section with findings ranked [high]/[medium]/[low]
  no_sync                 the sync skill never ran
  only_user_paths         psai and the installed stacks are untouched
  router_invoked          the agent used the request-router skill (Skill tool or reading its SKILL.md)
  no_workflow             no workflow node was entered
  role_used_skill <name>  a role agent (subagent) invoked the skill or read its SKILL.md
  role_model {role: id}   the agent started that role's subagent with that model (the Agent tool's model)
  first_question <regex>  the first fixed block the agent asked (kind: question) matches
  roles_no_route          role agents never invoked request-router or work, nor ran trace.sh, and the trace holds one
                          workflow run
Unexpected escalations or questions (no scripted answer) always fail.
"""
import glob
import os
import re
import subprocess

import yaml


def _sh(cmd, cwd):
    if not os.path.isdir(cwd):
        return 1, f"no {cwd}"
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
    final, text = log.get("final", "") or "", log.get("text") or ""
    tr_all = _trace(ctx["base"])
    starts = [i for i, t in enumerate(tr_all) if t.startswith("phase ")]
    tr = tr_all[starts[-1]:] if starts else tr_all
    path = [t.split()[1] for t in tr if t.startswith("node ")] or log.get("path", [])
    own, w, found = ctx["own"], ctx["work"], ctx.get("found") or {}
    add("no unexpected escalation or question", not log["unexpected"], "; ".join(log["unexpected"]))
    if "path_includes" in expect:
        add("path includes " + ",".join(expect["path_includes"]), _subseq(expect["path_includes"], path), " -> ".join(path))
    if expect.get("ends_terminal"):
        terms = set()
        for f in glob.glob(os.path.join(own, "skills", "workflow-*", "workflow.yaml")) + [
                x for s in ctx["stacks"] for x in glob.glob(os.path.join(s, "skills", "workflow-*", "workflow.yaml"))]:
            terms |= {k for k, v in ((yaml.safe_load(open(f)) or {}).get("nodes") or {}).items()
                      if isinstance(v, dict) and v.get("terminal")}
        add("path ends at a terminal", bool(path) and path[-1] in terms, " -> ".join(path) + f" (terminals: {sorted(terms)})")
    for n in expect.get("path_excludes", []):
        add(f"path excludes {n}", n not in path, " -> ".join(path))
    if "escalations" in expect:
        k, lim = len(log["escalations"]), expect["escalations"]
        add(f"escalations within {lim}", lim.get("min", 0) <= k <= lim.get("max", 99), f"{k}: {log['escalations']}")
    if "escalation_nodes" in expect:
        add("escalated from " + ",".join(expect["escalation_nodes"]),
            all(n in expect["escalation_nodes"] for n in log["escalations"]), str(log["escalations"]))
    for r in expect.get("roles_checked", []):
        add(f"check-diff ran for {r}", any(f"role={r} " in t for t in tr), f"{len(tr)} trace lines")
    for role in expect.get("boundary_held", []):
        rl = [t for t in tr if f"role={role} " in t]
        viol = sum("result=violation" in t for t in rl)
        add(f"{role} boundary held", bool(rl) and "result=ok" in rl[-1], f"{viol} violation(s) caught; last: {rl[-1] if rl else 'none'}")
    if "checks" in expect:
        rc, o = _sh(expect["checks"], w)
        add(f"checks pass: {expect['checks']}", rc == 0, o.strip().splitlines()[-1] if o.strip() else "")
    for s in expect.get("final_sections", []):
        add(f"final message has '{s}'", re.search(r"^#+\s*" + re.escape(s), final, re.M | re.I), "")
    for m in expect.get("mentions", []):
        add(f"agent mentions {m}", m.lower() in (text or final).lower(), final[-200:])
    for m in expect.get("answer_mentions", []):
        add(f"answer mentions {m}", m.lower() in final.lower(), final[-200:])
    if expect.get("unchanged"):
        rc, o = _sh("git status --porcelain && git rev-parse HEAD", w)
        add("work repo unchanged", o.strip().splitlines() == [ctx["head0"]], o.strip()[:200])
    for f in expect.get("work_files", []):
        add(f"work repo has {f}", os.path.exists(os.path.join(w, f)))
    if expect.get("no_push"):
        gl = os.path.join(ctx["base"], "gh.log")
        ghs = open(gl).read() if os.path.exists(gl) else ""
        add("no push, merge or PR", ctx["remote_refs"] == ctx["refs0"] and not re.search(r"\b(merge|create)\b", ghs),
            ghs.strip()[:200])
    if expect.get("own_exists"):
        add("the owner's stack exists", os.path.isdir(os.path.join(own, ".git")), own)
    for f in expect.get("files", []):
        add(f"own has {f}", glob.glob(os.path.join(own, f)), "")
    for d in expect.get("new_files_in", []):
        staged = [x for x in found.get("stage") or [] if x.startswith(d.rstrip("/") + "/")]
        rc, o = _sh(f"git log --name-only --format= main -- {d}", own)
        add(f"new file under {d}", staged or o.strip(), (", ".join(staged) or o.strip())[:200])
    if expect.get("workflow_named"):
        hits = glob.glob(os.path.join(own, "skills", f"workflow-*{expect['workflow_named']}*", "workflow.yaml"))
        add(f"own has a workflow skill named *{expect['workflow_named']}*", hits, ", ".join(hits))
    for role, v in (expect.get("may_change") or {}).items():
        files = glob.glob(os.path.join(own, "skills", "*", "roles", f"{role}.md"))
        ok = any(re.search(rf"^may_change:\s*{v}\s*(#.*)?$", open(f).read(), re.M) for f in files)
        add(f"{role} may_change: {v}", ok, ", ".join(files) or "no role file")
    for m in expect.get("rules_mention", []):
        files = glob.glob(os.path.join(own, "skills", "*-rules", "SKILL.md"))
        add(f"a rules skill mentions '{m}'", any(m.lower() in open(f).read().lower() for f in files), ", ".join(files))
    if expect.get("own_checks"):
        rc, o = _sh(f"{ctx['check']} .", own)
        bad = [ln for ln in o.splitlines() if "FAIL" in ln]
        add("own passes check.py", rc == 0, "; ".join(bad)[:400])
    if expect.get("staged"):
        add("staged, no other branch", (found.get("stage") or found.get("branches")) and not found.get("other"),
            str(found)[:300])
    for pre, n in (expect.get("branches") or {}).items():
        got = [b for b in found.get("branches") or [] if b.startswith(pre)]
        add(f"{n} branch(es) {pre}*", len(got) == n, ", ".join(found.get("branches") or []))
    if expect.get("retro_findings"):
        m = re.search(r"^#+\s*Retro\b(.*)", final, re.M | re.I | re.S)
        add("final message has ranked retro findings", m and re.search(r"\[(high|medium|low)\]", m.group(1), re.I),
            (m.group(0)[:300] if m else final[-300:]))
    if expect.get("no_sync"):
        cmd = re.search(r'"skill": "[^"]*\bsync"|skills/sync/SKILL\.md', text)
        add("sync never ran", not cmd, cmd.group(0) if cmd else "")
    if expect.get("only_user_paths"):
        changed = []
        for d in [ctx["psai"]] + ctx["stacks"]:
            _, o = _sh('git status --porcelain; [ "$(git rev-list --count HEAD)" = 1 ] || echo "new commits"', d)
            changed += [f"{os.path.basename(d)}: {ln}" for ln in o.splitlines() if ln.strip()]
        add("psai and the installed stacks are untouched", not changed, "; ".join(changed)[:300])
    if expect.get("router_invoked"):
        add("request-router invoked", re.search(r'"skill": "[^"]*request-router"|request-router/SKILL\.md', text), "")
    if expect.get("no_workflow"):
        add("no workflow ran", not path, " -> ".join(path))
    if expect.get("role_used_skill"):
        n, calls = expect["role_used_skill"], log.get("sub_calls") or []
        hit = [c for c in calls if re.search(rf'"skill": "([^"]*:)?{re.escape(n)}"|{re.escape(n)}/SKILL\.md', c)]
        add(f"a role used {n}", hit, f"{len(calls)} subagent tool calls")
    for role, mid in (expect.get("role_model") or {}).items():
        mine = [c for c in log.get("agent_calls") or [] if role in f"{c.get('description', '')} {c.get('prompt', '')}"[:400]]
        add(f"{role} delegated with model {mid}", any(c.get("model") == mid for c in mine),
            "; ".join(f"{c.get('description')}: model={c.get('model')}" for c in mine)[:300] or "no agent call for the role")
    if expect.get("first_question"):
        qs = [q for q in log.get("asked") or [] if q.startswith("question: ")]
        add(f"first question matches /{expect['first_question']}/", qs and re.search(expect["first_question"], qs[0], re.I),
            (qs[0] if qs else "no question asked")[:200])
    if expect.get("roles_no_route"):
        calls = log.get("sub_calls") or []
        bad = [c for c in calls if re.search(r'"skill": "[^"]*\b(request-router|work)"|(request-router|/work)/SKILL\.md|work/trace\.sh', c)]
        runs = sum(t.startswith("workflow ") for t in tr)
        add("role agents did not route", calls and not bad and runs == 1,
            f"{len(calls)} subagent tool calls, {len(bad)} routing: {'; '.join(bad)[:300]}; workflow runs in trace: {runs}")
    return out
