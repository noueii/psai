#!/usr/bin/env python3
"""Model per role (ADR 0011, section 8; Q5: tiers mapped per tool, with optional concrete ids).

A role's model is a tier (fast | balanced | strong) or a mapping of concrete ids per tool
({claude: opus, opencode: anthropic/claude-opus-5-5, pi: claude-opus-5-5, omp: claude-opus-5-5}).
Order, first set wins (a mapping without this tool counts as unset):
  1. the overlay's stack.yaml  models.roles["<stack>:<role>"]
  2. the role's frontmatter    model:
  3. the stack's stack.yaml    models.roles.<role>
  4. the stack's stack.yaml    models.default
  5. the tool's current model (nothing is passed)
A tier becomes an id through the overlay's models.tiers.<tool>.<tier> (`psai setup models` writes it), else the
framework's default map below.

  psai resolve model <stack>:<role> [--tool claude|opencode|pi|omp] [--json]
  psai setup models [--set <tool>.<tier>=<id> ...]
"""
import argparse
import json
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import resolve as res  # noqa: E402

TIERS = ("fast", "balanced", "strong")
TOOLS = ("claude", "opencode", "pi", "omp")
DEFAULT_TIERS = {
    "claude": {"fast": "haiku", "balanced": "sonnet", "strong": "opus"},
    "opencode": {"fast": "anthropic/claude-haiku-5-5", "balanced": "anthropic/claude-sonnet-5-5",
                 "strong": "anthropic/claude-opus-5-5"},
    "pi": {"fast": "claude-haiku-5-5", "balanced": "claude-sonnet-5-5", "strong": "claude-opus-5-5"},
    "omp": {"fast": "claude-haiku-5-5", "balanced": "claude-sonnet-5-5", "strong": "claude-opus-5-5"},
}
# How `work` passes a model when it delegates; None: the tool's delegation can't set one per call (verified against
# Claude Code, opencode 1.18.30, pi 0.80.2 and omp 18.11.0: opencode's and omp's task tools take an agent, not a model).
HOW = {"claude": "the Agent tool's model parameter", "pi": "pi -p --model <id>", "opencode": None, "omp": None}


def validate(value, where="model"):
    """Errors in a model value: a tier, or a mapping of tool -> id."""
    if isinstance(value, str):
        return [] if value in TIERS else [f"{where}: {value!r} is not a tier ({', '.join(TIERS)}) or a mapping of tool: id"]
    if isinstance(value, dict):
        errs = [f"{where}: unknown tool {k!r} (one of {', '.join(TOOLS)})" for k in value if k not in TOOLS]
        errs += [f"{where}.{k}: must be a model id" for k, v in value.items() if not isinstance(v, str) or not v.strip()]
        return errs
    return [f"{where}: must be a tier or a mapping of tool: id"]


def _fm(path):
    try:
        m = re.match(r"^---\n(.*?)\n---\n", open(path).read(), re.S)
        return (yaml.safe_load(m.group(1)) or {}) if m else {}
    except (OSError, yaml.YAMLError):
        return {}


def tiers(h):
    t = {k: dict(v) for k, v in DEFAULT_TIERS.items()}
    for tool, m in (((h.overlay.meta or {}).get("models") or {}).get("tiers") or {}).items():
        if isinstance(m, dict):
            t.setdefault(tool, {}).update({k: str(v) for k, v in m.items()})
    return t


def resolve_model(ref, tool="claude", frm=None, h=None):
    """{tool, id, tier, source, settable}; id None = the tool's current model."""
    h = h or res.home()
    r = res.resolve_all("role", ref, frm=frm, h=h)
    stack, name = r["stack"], res.rel_path("role", res.split_ref(ref)[1])[len("roles/"):-len(".md")]
    st = h.get(stack)
    over = ((h.overlay.meta or {}).get("models") or {}).get("roles") or {}
    smodels = (st.meta or {}).get("models") or {} if stack != res.OVERLAY else (h.overlay.meta or {}).get("models") or {}
    chain = [(f"your overlay's models.roles[{stack}:{name}]", over.get(f"{stack}:{name}")),
             (f"the role's frontmatter ({r['path']})", _fm(r["path"]).get("model")),
             (f"{stack}'s stack.yaml models.roles.{name}", (smodels.get("roles") or {}).get(name)),
             (f"{stack}'s stack.yaml models.default", smodels.get("default"))]
    for source, v in chain:
        if v is None or (isinstance(v, dict) and tool not in v):
            continue
        if isinstance(v, dict):
            return {"tool": tool, "id": str(v[tool]), "tier": None, "source": source, "settable": HOW[tool] is not None}
        if v in TIERS:
            return {"tool": tool, "id": tiers(h).get(tool, {}).get(v), "tier": v, "source": source,
                    "settable": HOW[tool] is not None}
    return {"tool": tool, "id": None, "tier": None, "source": "none set: the tool's current model", "settable": True}


def node_line(ref, frm, h):
    """The `model:` line psai node prints for a role: the id per tool (`psai resolve model --json` says where each
    comes from); the tools whose delegation can't set a model per call are named once."""
    ids, unset = [], []
    for t in TOOLS:
        m = resolve_model(ref, t, frm, h)
        if not m["id"]:
            continue
        if m["settable"]:
            ids.append(f"{t} {m['id']}" + (f" (tier {m['tier']})" if m["tier"] else ""))
        else:
            unset.append(t)
    if not ids and not unset:
        return "model: none set (the tool's current model)"
    tail = f"; {', '.join(unset)}: not settable per call (say so in the final report)" if unset else ""
    return "model: " + "; ".join(ids) + tail


def setup(h, sets=()):
    """Write the overlay's models.tiers: the framework's defaults, plus --set <tool>.<tier>=<id> changes."""
    p = os.path.join(h.overlay_path, "stack.yaml")
    meta = res.load_stack(h.overlay_path) or {}
    t = tiers(h)
    for s in sets:
        m = re.match(r"^([a-z]+)\.([a-z]+)=(.+)$", s)
        if not m or m.group(1) not in TOOLS or m.group(2) not in TIERS:
            raise ValueError(f"--set takes <tool>.<tier>=<id> (tools {', '.join(TOOLS)}; tiers {', '.join(TIERS)}): {s}")
        t.setdefault(m.group(1), {})[m.group(2)] = m.group(3)
    meta.setdefault("models", {})["tiers"] = t
    with open(p, "w") as f:
        yaml.safe_dump(meta, f, sort_keys=False)
    for tool in TOOLS:
        print(f"{tool}: " + ", ".join(f"{k}={t[tool][k]}" for k in TIERS) + ("" if HOW[tool] else "  (not settable per call)"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="psai resolve model")
    ap.add_argument("ref")
    ap.add_argument("--tool", default="claude", choices=TOOLS)
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        m = resolve_model(a.ref, a.tool, a.frm)
    except res.ResolveError as e:
        print(f"psai resolve model: {e.msg}", file=sys.stderr)
        return e.code
    print(json.dumps(m) if a.json else (m["id"] or "") + ("" if m["settable"] else "  (not settable per call in " + a.tool + ")"))
    return 0


def setup_main(argv):
    ap = argparse.ArgumentParser(prog="psai setup models")
    ap.add_argument("what", choices=["models"])
    ap.add_argument("--set", action="append", default=[], help="<tool>.<tier>=<id>, e.g. claude.strong=opus")
    a = ap.parse_args(argv)
    try:
        return setup(res.home(), a.set)
    except ValueError as e:
        print(f"psai setup models: {e}", file=sys.stderr)
        return 2
