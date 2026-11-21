#!/usr/bin/env python3
"""The engine's lookups, so the request-router and work skills never build paths (`psai route|node|trace|check-diff`).

  psai route                         the routing tree and each workflow's `when`, per stack, plus where the engine is
  psai node <workflow> <node>        a node's resolved files: its step and `read:` files; for a role, the brief, the
                                     brief's `read:` files, its knowledge and its skills (exit 3: a required skill is
                                     missing); then its edges
  psai trace <workflow> <node>       skills/work/trace.sh: record the move, refuse one that isn't an edge
  psai check-diff <workflow> <node> <base>   skills/work/check-diff.sh with that node's role brief

A workflow is `stack:name`, or a bare name when one stack has it. Everything resolves through resolve.py, with
--from set to the stack whose file holds each ref.
"""
import os
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import resolve as res  # noqa: E402
import skills as skillreg  # noqa: E402

FW = os.path.dirname(HERE)


def qualified(h, stack, name):
    """`stack:name`, or the bare name in single-root compat mode (one stack, nothing to tell apart)."""
    return name if h.compat else f"{stack}:{name}"


def _load(p):
    with open(p) as f:
        return yaml.safe_load(f) or {}


def _workflows(st):
    d = os.path.join(st.path, "workflows")
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d)
                  if f.endswith(".yaml") and not f.endswith(".cases.yaml") and not f.startswith("ROUTING"))


def route(h=None):
    h = h or res.home()
    out = [f"Engine: {res.resolve('skill', 'work', h=h)} (read it once a workflow is chosen). "
           f"Escalation block: {res.resolve('file', 'psai:skills/work/escalation.md', h=h)}.", ""]
    any_wf = False
    for st in h.content_stacks():
        wfs = _workflows(st)
        if not wfs:
            continue
        any_wf = True
        desc = st.meta.get("description")
        out.append(f"## {st.name}" + (f": {' '.join(str(desc).split())}" if desc and not h.compat else ""))
        rp = os.path.join(st.path, "workflows", "ROUTING.yaml")
        if os.path.exists(rp):
            out += ["Routing tree (workflows/ROUTING.yaml):", "```yaml",
                    yaml.safe_dump(_load(rp).get("tree"), sort_keys=False, allow_unicode=True).rstrip(), "```"]
        out.append("Workflows:")
        for p in wfs:
            wf = _load(p)
            name = wf.get("name", os.path.basename(p)[:-5])
            out.append(f"- {qualified(h, st.name, name)}: {' '.join(str(wf.get('when', '')).split())}")
        out.append("")
    if not any_wf:
        out.append("No workflows yet (customize-harness creates the first one).")
    print("\n".join(out).rstrip())
    return 0


def _reads(path, frm, h):
    fm = skillreg._fm(path)
    out = []
    for r in fm.get("read") or []:
        try:
            out.append(res.resolve("file", r, frm=frm, h=h))
        except res.ResolveError as e:
            out.append(f"MISSING {r} ({e.msg})")
    return out


def node(wf_ref, nid, h=None):
    h = h or res.home()
    w = res.resolve_all("workflow", wf_ref, h=h)
    stack, wf = w["stack"], _load(w["path"])
    nodes = wf.get("nodes") or {}
    if nid not in nodes:
        print(f"psai node: {nid!r} is not a node of {wf_ref}", file=sys.stderr)
        return 3
    n = nodes[nid] or {}
    out = [f"workflow: {qualified(h, stack, wf.get('name', wf_ref))} ({w['path']})", f"node: {nid}"]
    rc, step = 0, None
    if n.get("step"):
        s = res.resolve_all("file", n["step"], frm=stack, h=h)
        step = s["path"]
        out.append(f"step: {step}")
        out += [f"  read: {p}" for p in _reads(step, s["stack"], h)]
    if n.get("role"):
        b = res.resolve_all("role", str(n["role"]), frm=stack, h=h)
        rname = res.rel_path("role", res.split_ref(str(n["role"]))[1])[len("roles/"):-3]
        out.append(f"role: {rname} (stack {b['stack']}); delegate it to a FRESH agent")
        out.append(f"  brief: {b['path']}")
        out += [f"  read: {p}" for p in _reads(b["path"], b["stack"], h)]
        try:
            k = res.resolve_all("knowledge", f"{b['stack']}:roles/{rname}/INDEX.md", h=h)
            out += [f"  knowledge: {p}" for p in k["layers"]]
        except res.ResolveError:
            out.append("  knowledge: none yet")
        text, miss_r, _ = skillreg.brief(h.overlay_path, [b["path"]] + ([step] if step else []),
                                         project=skillreg.project_root())
        out += ["  " + line for line in text.splitlines()]
        rc = 3 if miss_r else 0
        out.append(f"  after it returns: psai check-diff {wf_ref} {nid} \"$base\"")
    if n.get("human"):
        out.append("human: ask with the fixed block, kind review, and wait")
    if n.get("skill"):
        out.append(f"skill: {n['skill']}")
    if "handoff" in n:
        tgt = res.resolve_all("workflow", str(n["handoff"]), frm=stack, h=h)
        out.append(f"handoff: continue in {qualified(h, tgt['stack'], res.split_ref(str(n['handoff']))[1])} at its start")
    if "return" in n:
        out.append("escalate: emit the block (kind escalation), wait, then resume the node that asked")
    if n.get("terminal"):
        out.append("terminal: run the retro if none ran, then the final report")
    for e in n.get("next") or []:
        out.append(f"next: {e.get('when', '(default)')} -> {e.get('to')}" + (f" (max {e['max']})" if e.get("max") else ""))
    print("\n".join(out))
    return rc


def role_brief(wf_ref, nid, h=None):
    h = h or res.home()
    w = res.resolve_all("workflow", wf_ref, h=h)
    n = (_load(w["path"]).get("nodes") or {}).get(nid) or {}
    if not n.get("role"):
        raise res.ResolveError(res.NOT_FOUND, f"node {nid} of {wf_ref} has no role")
    return res.resolve("role", str(n["role"]), frm=w["stack"], h=h)


def main(cmd, argv):
    try:
        if cmd == "route":
            return route()
        if cmd == "node":
            if len(argv) != 2:
                print("usage: psai node <workflow> <node>", file=sys.stderr)
                return 2
            return node(*argv)
        if cmd == "trace":
            return subprocess.run(["bash", os.path.join(FW, "skills", "work", "trace.sh"), *argv]).returncode
        if cmd == "check-diff":
            if len(argv) == 3:
                argv = [role_brief(argv[0], argv[1]), argv[2]]
            return subprocess.run(["bash", os.path.join(FW, "skills", "work", "check-diff.sh"), *argv]).returncode
    except res.ResolveError as e:
        print(f"psai {cmd}: {e.msg}", file=sys.stderr)
        return e.code
    print(f"psai: unknown engine command {cmd}", file=sys.stderr)
    return 2
