"""Workflow checks for check.py (maintainer-only): refs, graph rules and simulator cases.

A repo's workflows are its `skills/workflow-*/workflow.yaml`. A ref is `path` (in the folder of the skill that holds
the naming file) or `skill:path` (in that skill's folder). Skills are looked up in the repo and in any `--with` repos;
a ref to a skill found in neither is reported as "not checked", not as an error.
"""
import os
import re

import yaml

PSAI_SKILLS = {"request-router", "work", "customize-harness", "capture-knowledge", "retro", "sync"}
MAY_CHANGE = {"anything", "tests", "nothing"}
TIERS = {"fast", "balanced", "strong"}
STEP_CAP = 500


def frontmatter(path):
    m = re.match(r"^---\r?\n(.*?)\r?\n---", open(path, encoding="utf-8").read(), re.S)
    return (yaml.safe_load(m.group(1)) or {}) if m else {}


def skills_in(repos):
    """{skill name: folder} for every skill in these repos (first wins)."""
    out = {}
    for repo in repos:
        base = os.path.join(repo, "skills")
        for d in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            if os.path.isfile(os.path.join(base, d, "SKILL.md")):
                out.setdefault(d, os.path.join(base, d))
    return out


class Refs:
    def __init__(self, skills):
        self.skills, self.external = skills, set()

    def resolve(self, ref, here):
        """(path or None, error or None). `here` is the folder of the skill holding the naming file."""
        if not isinstance(ref, str) or not ref:
            return None, f"not a ref: {ref!r}"
        if ":" in ref:
            skill, path = ref.split(":", 1)
            if skill not in self.skills:
                self.external.add(skill)
                return None, None
            folder = self.skills[skill]
        else:
            folder, path = here, ref
        full = os.path.normpath(os.path.join(folder, path))
        if not full.startswith(os.path.normpath(folder) + os.sep):
            return None, f"{ref}: leaves its skill folder"
        return (full, None) if os.path.isfile(full) else (None, f"{ref}: no such file")


def back_edges(wf):
    order = {nid: i for i, nid in enumerate(wf["nodes"])}
    out = []
    for nid, n in wf["nodes"].items():
        for e in (n or {}).get("next") or []:
            to = e.get("to")
            if to in order and order[to] <= order[nid] and "return" not in (wf["nodes"][to] or {}):
                out.append((nid, e))
    return out


def edge_limit(wf, nid, edge):
    if edge.get("max") is not None:
        return edge["max"]
    if (wf["nodes"][nid] or {}).get("human"):
        return None
    if any(e is edge for n, e in back_edges(wf) if n == nid):
        return (wf.get("defaults") or {}).get("max")
    return None


def is_end(n):
    return bool(n.get("terminal")) or "return" in n or "handoff" in n


def validate(folder, refs, skills):
    """Errors in one workflow skill folder."""
    errs = []
    name = os.path.basename(folder)
    fm = frontmatter(os.path.join(folder, "SKILL.md"))
    if not str(fm.get("description", "")).startswith("Workflow:"):
        errs.append(f"{name}: the SKILL.md description must start with 'Workflow:'")
    path = os.path.join(folder, "workflow.yaml")
    if not os.path.isfile(path):
        return errs + [f"{name}: no workflow.yaml"]
    try:
        wf = yaml.safe_load(open(path)) or {}
    except yaml.YAMLError as e:
        return errs + [f"{name}: workflow.yaml doesn't parse: {str(e).splitlines()[0]}"]
    nodes = wf.get("nodes") or {}
    if not isinstance(nodes, dict) or not nodes:
        return errs + [f"{name}: no nodes"]
    if wf.get("start") not in nodes:
        errs.append(f"{name}: start {wf.get('start')!r} is not a node")
    ex = (wf.get("defaults") or {}).get("on_exhaust")
    if ex is not None and ex not in nodes:
        errs.append(f"{name}: defaults.on_exhaust {ex!r} is not a node")

    def check_file(ref, what, role=False):
        p, why = refs.resolve(ref, folder)
        if why:
            errs.append(f"{name}: {what}: {why}")
        if not p:
            return
        try:
            f = frontmatter(p)
        except yaml.YAMLError as e:
            errs.append(f"{name}: {ref}: frontmatter doesn't parse: {str(e).splitlines()[0]}")
            return
        here = refs.skills[ref.split(":", 1)[0]] if ":" in ref else folder   # reads are relative to the file's skill
        reads = f.get("read") or []
        if not isinstance(reads, list):
            errs.append(f"{name}: {ref}: read: must be a list")
            reads = []
        for r in reads:
            _, w = refs.resolve(r, here)
            if w:
                errs.append(f"{name}: {ref}: read: {w}")
        sk = f.get("skills") or {}
        if not isinstance(sk, dict) or set(sk) - {"required", "optional"}:
            errs.append(f"{name}: {ref}: skills: must be {{required: [...], optional: [...]}}")
        for s in (sk.get("required") or []) if isinstance(sk, dict) else []:
            if s not in skills and s not in PSAI_SKILLS:
                refs.external.add(s)
        if role:
            if f.get("may_change") not in MAY_CHANGE:
                errs.append(f"{name}: {ref}: may_change must be one of {sorted(MAY_CHANGE)}")
            m = f.get("model")
            if m is not None and not (m in TIERS or (isinstance(m, dict) and all(isinstance(v, str) for v in m.values()))):
                errs.append(f"{name}: {ref}: model must be {sorted(TIERS)} or ids per tool")

    for nid, n in nodes.items():
        n = n or {}
        if is_end(n):
            if "handoff" in n and n["handoff"] not in skills:
                refs.external.add(n["handoff"])
            continue
        if "step" in n:
            check_file(n["step"], f"{nid}: step")
        elif not n.get("skill"):
            errs.append(f"{name}: {nid}: needs a step (or skill:)")
        if n.get("skill") and n["skill"] not in skills and n["skill"] not in PSAI_SKILLS:
            refs.external.add(n["skill"])
        if n.get("role"):
            check_file(n["role"], f"{nid}: role", role=True)
        nxt = n.get("next") or []
        if not nxt:
            errs.append(f"{name}: {nid}: no next edges")
        for e in nxt:
            if e.get("to") not in nodes:
                errs.append(f"{name}: {nid}: edge to unknown node {e.get('to')!r}")
    if errs:
        return errs
    # graph rules
    seen, todo = set(), [wf["start"]]
    while todo:
        x = todo.pop()
        if x in seen:
            continue
        seen.add(x)
        todo += [e["to"] for e in (nodes[x] or {}).get("next") or []]
    for x in nodes:
        if x not in seen:
            errs.append(f"{name}: {x} is unreachable from start")
    ends = {x for x in nodes if is_end(nodes[x] or {})}
    changed = True
    while changed:
        changed = False
        for x in nodes:
            if x not in ends and any(e["to"] in ends for e in (nodes[x] or {}).get("next") or []):
                ends.add(x)
                changed = True
    for x in nodes:
        if x not in ends:
            errs.append(f"{name}: no path from {x} can end (terminal, return or handoff)")
    for nid, e in back_edges(wf):
        if not (nodes[nid] or {}).get("human") and edge_limit(wf, nid, e) is None:
            errs.append(f"{name}: the loop {nid} -> {e['to']} has no limit (max on the edge, or defaults.max)")
    return errs


def run(wf, take=None):
    take = {k: list(v) for k, v in (take or {}).items()}
    nodes, exhaust = wf["nodes"], (wf.get("defaults") or {}).get("on_exhaust")
    path, counts, cur, asker = [], {}, wf["start"], None
    while len(path) < STEP_CAP:
        path.append(cur)
        n = nodes[cur] or {}
        if n.get("terminal") or "return" in n:
            return path, cur, asker
        if "handoff" in n:
            return path, f"handoff:{n['handoff']}", asker
        edges, want = n["next"], take.get(cur, [])
        if want:
            w = want.pop(0)
            match = [e for e in edges if e.get("when") == w]
            if not match:
                raise ValueError(f"{cur}: no edge with when {w!r}")
            edge = match[0]
        else:
            edge = edges[-1]
        key = (cur, edge["to"], edge.get("when"))
        counts[key] = counts.get(key, 0) + 1
        limit = edge_limit(wf, cur, edge)
        if limit is not None and counts[key] > limit:
            asker, cur = cur, exhaust
            continue
        if "return" in (nodes.get(edge["to"]) or {}):
            asker = cur
        cur = edge["to"]
    raise RuntimeError("step cap reached (an endless loop?)")


def simulate(repo, folder):
    """[(case name, ok, detail)] for evals/cases/<workflow skill>.yaml."""
    name = os.path.basename(folder)
    cpath = os.path.join(repo, "evals", "cases", f"{name}.yaml")
    if not os.path.isfile(cpath):
        return [(f"{name}: evals/cases/{name}.yaml", False, "missing")]
    wf = yaml.safe_load(open(os.path.join(folder, "workflow.yaml")))
    out = []
    for case in yaml.safe_load(open(cpath)) or []:
        try:
            p, end, asker = run(wf, case.get("take"))
            ok = any(k in case for k in ("path", "ends"))
            ok = ok and case.get("path", p) == p and case.get("ends", end) == end and case.get("asker", asker) == asker
            detail = " -> ".join(p) + (f" (asker {asker})" if asker else "")
        except (ValueError, RuntimeError, KeyError) as e:
            ok, detail = False, str(e)
        out.append((f"{name}: {case.get('name')}", ok, detail))
    return out
