#!/usr/bin/env python3
"""The merged routing index (ADR 0011, section 4): every enabled stack's description, priority, instructions/stack.md,
routing tree and workflows (`stack:name`, `when`), cached in <state>/index.json and rebuilt when a stack's files change.

  psai index            rebuild it and print a one-line summary per stack
  psai route            print it for the request-router skill (engine.py)

The overlay `nostack` comes first and is never collapsed or disabled. Its stack.yaml may set:
  disable:  [acme:release, acme]                       drop a workflow, or a whole stack
  priority: {acme: 70}                                 replace a stack's routing.priority
  prefer:   [{if: "<kind of task>", use: acme:review}]  the first tie-break when several workflows fit
A stack's file is read through the overlay's override when there is one (overlay/overrides/<stack>/...).
"""
import hashlib
import json
import os
import sys

import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import resolve as res  # noqa: E402

BUDGET = 300          # words of workflow lines in the nudge
STACK_MD_CAP = 60     # words of a stack's instructions/stack.md in the nudge


def _load(p):
    try:
        with open(p) as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _layer(h, st, rel):
    """A stack's file, through the overlay's override when there is one."""
    if st.name not in res.RESERVED:
        o = os.path.join(h.overlay_path, "overrides", st.name, rel)
        if os.path.exists(o):
            return o
    return os.path.join(st.path, rel)


def _wf_names(h, st):
    """The stack's own workflow names (an override replaces a file; it never adds a workflow)."""
    d = os.path.join(st.path, "workflows")
    return sorted(f[:-5] for f in (os.listdir(d) if os.path.isdir(d) else [])
                  if f.endswith(".yaml") and not f.endswith(".cases.yaml") and not f.startswith("ROUTING"))


def _qualify(tree, stack, compat):
    """The routing tree with each `workflow:` leaf as stack:name (a bare leaf means this stack's workflow)."""
    if compat or not isinstance(tree, dict):
        return tree
    t = dict(tree)
    if "workflow" in t and not res.split_ref(str(t["workflow"]))[0]:
        t["workflow"] = f"{stack}:{t['workflow']}"
    if isinstance(t.get("answers"), list):
        t["answers"] = [dict(a, then=_qualify(a.get("then"), stack, compat)) if isinstance(a, dict) else a for a in t["answers"]]
    return t


def settings(h):
    meta = h.overlay.meta or {}
    dis = [str(x) for x in meta.get("disable") or []]
    return {"disable": dis, "priority": dict(meta.get("priority") or {}), "prefer": list(meta.get("prefer") or [])}


def _sig(h):
    """A cheap key: path, size and mtime of every file the index reads (stack.yaml, instructions/stack.md, workflows,
    overrides of them, the overlay's stack.yaml and stacks.yaml)."""
    parts = []
    for st in h.content_stacks():
        for d in (st.path, os.path.join(h.overlay_path, "overrides", st.name)):
            for rel in ("stack.yaml", "stacks.yaml", os.path.join("instructions", "stack.md")):
                parts.append(os.path.join(d, rel))
            wd = os.path.join(d, "workflows")
            parts += [os.path.join(wd, f) for f in sorted(os.listdir(wd))] if os.path.isdir(wd) else []
    out = []
    for p in parts:
        try:
            s = os.stat(p)
            out.append(f"{p}:{s.st_size}:{s.st_mtime_ns}")
        except OSError:
            pass
    return hashlib.sha256("\n".join(out).encode()).hexdigest()[:16]


def build(h=None):
    h = h or res.home()
    conf = settings(h)
    stacks = []
    for st in h.content_stacks():
        overlay = st.name == res.OVERLAY
        if not overlay and st.name in conf["disable"]:
            continue
        meta = st.meta or {}
        md = _layer(h, st, os.path.join("instructions", "stack.md"))
        text = " ".join(open(md).read().split()) if os.path.exists(md) else ""
        if len(text.split()) > STACK_MD_CAP:
            text = " ".join(text.split()[:STACK_MD_CAP]) + " ..."
        wfs = []
        for name in _wf_names(h, st):
            q = name if h.compat else f"{st.name}:{name}"
            if not overlay and q in conf["disable"]:
                continue
            path = _layer(h, st, os.path.join("workflows", f"{name}.yaml"))
            wf = _load(path)
            wfs.append({"name": wf.get("name", name), "qualified": q, "path": path,
                        "when": " ".join(str(wf.get("when", "")).split())})
        tree = _qualify(_load(_layer(h, st, os.path.join("workflows", "ROUTING.yaml"))).get("tree"), st.name, h.compat)
        prio = conf["priority"].get(st.name, st.priority if not overlay else None)
        stacks.append({"name": st.name, "overlay": overlay, "description": " ".join(str(meta.get("description", "")).split()),
                       "priority": prio, "order": st.order, "instructions": text, "workflows": wfs, "tree": tree})
    return {"key": _sig(h), "compat": h.compat, "prefer": conf["prefer"], "disable": conf["disable"], "stacks": stacks}


def load(h=None):
    """The index, from the cache when nothing it reads has changed (a single-root home is built fresh: no cache)."""
    h = h or res.home()
    if h.compat:
        return build(h)
    cache = os.path.join(h.state, "index.json")
    key = _sig(h)
    try:
        with open(cache) as f:
            idx = json.load(f)
        if idx.get("key") == key and idx.get("compat") == h.compat:
            return idx
    except (OSError, ValueError):
        pass
    idx = build(h)
    try:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        tmp = f"{cache}.tmp{os.getpid()}"
        with open(tmp, "w") as f:
            json.dump(idx, f, indent=1, sort_keys=True)
        os.replace(tmp, cache)
    except OSError:
        pass  # a read-only state folder never breaks the nudge
    return idx


def ranked(idx):
    """The overlay first, then the stacks by priority (higher first), then their stacks.yaml order."""
    return sorted(idx["stacks"], key=lambda s: (not s["overlay"], -(s["priority"] or 0), s["order"]))


def wf_line(s, w):
    return f"- {w['qualified']}: {w['when']}"


def nudge_lines(idx, budget=BUDGET):
    """(workflow lines, stack rule blocks, collapsed?) for the nudge, within the word budget: over it, stacks collapse
    to one line each, the lowest priority first (the overlay never)."""
    order = ranked(idx)
    collapsed = set()
    words = lambda: sum(len(line.split()) for line in render(order, collapsed)[0])
    for s in reversed(order):
        if words() <= budget:
            break
        if not s["overlay"] and s["workflows"]:
            collapsed.add(s["name"])
    lines, rules = render(order, collapsed)
    return lines, rules, bool(collapsed)


def render(order, collapsed):
    lines, rules = [], []
    for s in order:
        if not s["workflows"]:
            continue
        if s["name"] in collapsed:
            lines.append(f"- {s['name']} ({len(s['workflows'])} workflows): {s['description']}")
            continue
        lines += [wf_line(s, w) for w in s["workflows"]]
        if s["instructions"] and not s["overlay"]:
            rules.append(f"## {s['name']} rules\n{s['instructions']}")
    return lines, rules


def main(argv=None):
    h = res.home()
    idx = build(h)
    try:
        os.makedirs(h.state, exist_ok=True)
        with open(os.path.join(h.state, "index.json"), "w") as f:
            json.dump(idx, f, indent=1, sort_keys=True)
    except OSError as e:
        print(f"psai index: can't write the cache: {e}", file=sys.stderr)
    for s in ranked(idx):
        print(f"{s['name']}: {len(s['workflows'])} workflow(s), priority {s['priority']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
