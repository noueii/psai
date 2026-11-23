#!/usr/bin/env python3
"""Run eval scenarios headless in Claude Code, with a scripted fake owner. Called by evals/run.sh.

Each run gets a throwaway directory, set up the way a consumer installs psai 4 (ADR 0012):
- psai/          the shipped part of this repo (skills, manifests, hooks, extensions), loaded with --plugin-dir;
- stacks/<name>/ copies of the scenario's `stacks:` (test stacks in evals/fixtures/), each loaded with --plugin-dir;
- own/           the owner's stack, where PSAI_STACK points: scaffolded from customize-harness's template as `mine`
                 (plus any `own:` fixture folders copied over it), or absent with `own: none`; loaded with
                 --plugin-dir when it has skills;
- work/          a copy of the fixture repo, a git repo whose origin is remote.git (a local bare repo);
- bin/gh         a shim that logs and refuses, so nothing reaches GitHub;
- trace.log      trace.sh's and check-diff.sh's lines (PSAI_TRACE).
`strip: [stacks/<name>/<path>]` removes a path from the run's copy (e.g. a skill a role requires).

The real HOME is only read in place by Claude Code for its own login. Nothing is copied from it and nothing is
installed into it: the plugins are loaded for the run only (--plugin-dir), with project settings only.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "graders"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import grade  # noqa: E402

BLOCK = re.compile(r"<<<HARNESS\s*\n(.*?)\n\s*>>>", re.S)
IGNORE = shutil.ignore_patterns(".git", "results", "__pycache__")
SHIPPED = ("skills", ".claude-plugin", "hooks", "extensions", "plugin.json", "package.json")
GIT_ENV = dict(GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@local", GIT_COMMITTER_NAME="eval",
               GIT_COMMITTER_EMAIL="eval@local")


def sh(cmd, cwd, check=True):
    return subprocess.run(cmd, cwd=cwd, shell=True, check=check, text=True, env=dict(os.environ, **GIT_ENV),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def git_init(path, msg="fixture"):
    sh(f"git init -q -b main && git add -A && git commit -qm '{msg}'", path)


def copy_layers(srcs, dest):
    for i, s in enumerate([srcs] if isinstance(srcs, str) else srcs):
        shutil.copytree(os.path.join(ROOT, "evals", "fixtures", s), dest, ignore=IGNORE, dirs_exist_ok=i > 0)


def scaffold_own(dest, layers):
    """The owner's stack `mine`, scaffolded the way customize-harness does it, plus fixture layers."""
    shutil.copytree(os.path.join(ROOT, "skills", "customize-harness", "template"), dest)
    for f in os.listdir(dest):
        if f.startswith("dot-"):
            os.rename(os.path.join(dest, f), os.path.join(dest, "." + f[4:]))
    for root, _, files in os.walk(dest):
        for f in files:
            p = os.path.join(root, f)
            t = open(p).read()
            for a, b in (("__NAME__", "mine"), ("__REPO__", "owner/mine"), ("__DESCRIPTION__", "The owner's stack."),
                         ("__AUTHOR__", "owner")):
                t = t.replace(a, b)
            open(p, "w").write(t)
    if layers:
        copy_layers(layers, dest)
    git_init(dest, "mine: new psai stack")


def prepare(scn, base):
    p = os.path.join(base, "psai")
    os.makedirs(p)
    for x in SHIPPED:
        s = os.path.join(ROOT, x)
        (shutil.copytree if os.path.isdir(s) else shutil.copy2)(s, os.path.join(p, x))
    git_init(p, "psai")
    stacks = []
    for name, fx in (scn.get("stacks") or {}).items():
        d = os.path.join(base, "stacks", name)
        copy_layers(fx, d)
        git_init(d, name)
        stacks.append(d)
    own = os.path.join(base, "own")
    if scn.get("own") != "none":
        scaffold_own(own, scn.get("own"))
    for rel in scn.get("strip") or []:  # hide something from the run, e.g. a stack's skill
        shutil.rmtree(os.path.join(base, rel), ignore_errors=True)
        top = os.path.join(base, *rel.split("/")[:2])
        sh("git add -A && git commit -qm strip", top, check=False)
    w = os.path.join(base, "work")
    shutil.copytree(os.path.join(ROOT, "evals", "fixtures", scn["fixture"]), w, ignore=IGNORE)
    git_init(w)
    sh(f"git init -q --bare {base}/remote.git && git remote add origin {base}/remote.git && git push -q origin main", w)
    b = os.path.join(base, "bin")
    os.makedirs(b)
    with open(os.path.join(b, "gh"), "w") as f:
        f.write(f'#!/bin/sh\necho "gh $*" >> {base}/gh.log\necho "gh is disabled in evals" >&2\nexit 1\n')
    os.chmod(os.path.join(b, "gh"), 0o755)
    return p, stacks, own, w


def remote_refs(base):
    return sh("git for-each-ref --format='%(refname) %(objectname)'", os.path.join(base, "remote.git")).stdout


# ---------- fake owner ----------
def parse_block(text):
    m = None
    for m in BLOCK.finditer(text or ""):
        pass
    if not m:
        return None
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip().lower()] = v.strip()
    return fields


def owner_answer(owner, block, log):
    kind, q = block.get("kind", "escalation"), block.get("question", "")
    log.setdefault("asked", []).append(f"{kind}: {q}")
    if kind == "review":
        log["reviews"] += 1
        return owner.get("review", "Approved.")
    rules = owner.get("answers" if kind == "question" else "escalations", []) or []
    if kind == "question":
        log["questions"] += 1
    else:
        log["escalations"].append(block.get("node", "?"))
    for r in rules:
        if re.search(r["match"], q, re.I):
            return r["answer"]
    if kind == "question" and owner.get("default"):
        return owner["default"]
    log["unexpected"].append(f"{kind} at {block.get('node')}: {block.get('question')}")
    return "I can't answer that. Decide yourself, log the decision, and carry on."


# ---------- Claude Code ----------
class Claude:
    def __init__(self, plugins, cwd, env, model, budget, base):
        args = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                "--setting-sources", "project", "--no-session-persistence", "--strict-mcp-config",
                "--permission-mode", "bypassPermissions", "--add-dir", base, "--model", model,
                "--max-budget-usd", str(budget)]
        for p in plugins:
            args += ["--plugin-dir", p]
        self.p = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True)
        self.texts, self.sub_calls, self.agent_calls, self.cost = [], [], [], 0.0
        self.raw = open(os.path.join(base, "stream.jsonl"), "a")

    def turn(self, message):
        self.p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": message}}) + "\n")
        self.p.stdin.flush()
        for line in self.p.stdout:
            self.raw.write(line)
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._collect(d)
            if d.get("type") == "result":
                self.cost = d.get("total_cost_usd") or self.cost
                return self._drain(d.get("result") or "")
        return None

    def _collect(self, d):
        if d.get("type") != "assistant":
            return
        for c in d["message"].get("content", []):
            if d.get("parent_tool_use_id"):  # a subagent (role agent): keep its tool calls for roles_no_route
                if c.get("type") == "tool_use":
                    self.sub_calls.append(json.dumps({"name": c.get("name"), "input": c.get("input", {})}))
            elif c.get("type") == "text":
                self.texts.append(c["text"])
            elif c.get("type") == "tool_use":
                self.texts.append(json.dumps(c.get("input", {})).replace("\\n", "\n"))
                if c.get("name") in ("Agent", "Task"):
                    self.agent_calls.append(c.get("input", {}))

    def _drain(self, result, idle=120):
        """If background agents are still running, the session continues on its own: keep reading until idle."""
        import select
        done = lambda res: bool(BLOCK.search(res)) or "[harness] node: ready" in "\n".join(self.texts[-5:]) + res
        if done(result):
            return result
        while True:
            r, _, _ = select.select([self.p.stdout], [], [], idle)
            if not r:
                return result
            line = self.p.stdout.readline()
            if not line:
                return result
            self.raw.write(line)
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._collect(d)
            if d.get("type") == "result":
                self.cost = d.get("total_cost_usd") or self.cost
                result = d.get("result") or ""
                if done(result):
                    return result
                idle = 60

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=30)
        except Exception:
            self.p.kill()


def run_phase(phase, plugins, own, w, base, model, budget):
    cwd = own if phase.get("cwd") == "own" and os.path.isdir(own) else w
    env = dict(os.environ, PSAI_STACK=own, PSAI_TRACE=os.path.join(base, "trace.log"),
               PATH=os.path.join(base, "bin") + os.pathsep + os.environ["PATH"], **GIT_ENV)
    owner = phase.get("owner") or {}
    log = {"reviews": 0, "questions": 0, "escalations": [], "unexpected": [], "turns": 0}
    agent = Claude(plugins, cwd, env, model, budget, base)
    msg, final, t0 = phase["task"], "", time.time()
    try:
        while log["turns"] < owner.get("max_turns", 10):
            log["turns"] += 1
            out = agent.turn(msg)
            if out is None:
                log["unexpected"].append("tool exited")
                break
            final = out
            block = parse_block(out)
            if not block:
                break
            msg = owner_answer(owner, block, log)
        else:
            log["unexpected"].append("turn limit reached")
    finally:
        agent.close()
    text = "\n".join(agent.texts)
    log.update(seconds=round(time.time() - t0), cost=round(agent.cost, 4), final=final, text=text,
               sub_calls=agent.sub_calls, agent_calls=agent.agent_calls,
               path=re.findall(r"\[harness\] node: ([A-Za-z0-9_-]+)", text))
    return log


def own_state(own):
    """What the run left in the owner's stack: the stage worktree's changes and the psai/ branches."""
    if not os.path.isdir(os.path.join(own, ".git")):
        return {"exists": False, "stage": [], "branches": [], "other": []}
    stage = os.path.join(own, ".git", "psai-stage")
    files = []
    if os.path.isdir(stage):
        st = sh("git status --porcelain", stage, check=False).stdout.splitlines()
        cm = sh("git diff --name-only main...HEAD", stage, check=False).stdout.splitlines()
        files = sorted({ln[3:] for ln in st if ln.strip()} | {ln for ln in cm if ln.strip()})
    brs = sh("git branch --format='%(refname:short)'", own).stdout.split()
    return {"exists": True, "stage": files, "branches": [b for b in brs if b.startswith("psai/") and b != "psai/stage"],
            "stage_branch": "psai/stage" in brs, "other": [b for b in brs if b != "main" and not b.startswith("psai/")]}


def merge_staged(own, found):
    """Stand in for the owner merging the retro's PR, so later phases install what was built."""
    stage = os.path.join(own, ".git", "psai-stage")
    if found.get("stage") and os.path.isdir(stage):
        sh("git add -A && git commit -qm 'eval: staged' || true", stage, check=False)
    branch = (found.get("branches") or [None])[-1] or ("psai/stage" if found.get("stage_branch") else None)
    if branch:
        sh(f"git merge -q --no-edit {branch}", own, check=False)


def run_scenario(path, model, budget, keep, stack=None):
    scn = yaml.safe_load(open(path))
    if stack:  # a stack's own scenario: that stack is loaded (and its own fixtures come first)
        scn.setdefault("stacks", {os.path.basename(stack.rstrip("/")): stack})
        if os.path.isdir(os.path.join(stack, "evals", "fixtures", scn["fixture"])):
            scn["fixture"] = os.path.join(stack, "evals", "fixtures", scn["fixture"])
    phases = scn.get("phases") or [{k: scn[k] for k in ("task", "owner", "expect") if k in scn}]
    base = tempfile.mkdtemp(prefix=f"psai-eval-{scn['name']}-")
    psai, stacks, own, w = prepare(scn, base)
    refs0, head0 = remote_refs(base), sh("git rev-parse HEAD", w).stdout.strip()
    results, ok = [], True
    for ph in phases:
        open(os.path.join(base, "trace.log"), "a").write(f"phase {ph.get('name', 'main')}\n")
        has_own = os.path.isdir(os.path.join(own, "skills")) and any(
            os.path.isfile(os.path.join(own, "skills", d, "SKILL.md")) for d in os.listdir(os.path.join(own, "skills")))
        log = run_phase(ph, [psai] + stacks + ([own] if has_own else []), own, w, base, model, budget)
        found = own_state(own)
        ctx = dict(base=base, own=own, work=w, psai=psai, stacks=stacks, refs0=refs0, head0=head0, found=found,
                   remote_refs=remote_refs(base), check=f"python3 {ROOT}/scripts/check.py")
        if ph.get("merge"):  # the owner merges what was staged before grading (and before later phases)
            merge_staged(own, found)
        checks = grade.grade(ph.get("expect") or {}, log, ctx)
        ok = ok and all(c[1] for c in checks)
        tr = open(os.path.join(base, "trace.log")).read().split(f"phase {ph.get('name', 'main')}\n")[-1].splitlines()
        results.append({"phase": ph.get("name", "main"), "seconds": log["seconds"], "cost_usd": log["cost"],
                        "turns": log["turns"], "path": [t.split()[1] for t in tr if t.startswith("node ")] or log["path"],
                        "role_checks": [t.replace("check-diff ", "") for t in tr if t.startswith("check-diff ")],
                        "escalations": log["escalations"], "questions": log["questions"], "reviews": log["reviews"],
                        "unexpected": log["unexpected"], "own": found, "final_message": (log["final"] or "")[-1500:],
                        "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]})
        if not ok:
            break
    summary = {"scenario": scn["name"], "level": scn.get("level"), "tool": "claude", "model": model, "passed": ok,
               "seconds": sum(r["seconds"] for r in results), "cost_usd": round(sum(r["cost_usd"] for r in results), 4),
               "phases": results, "workdir": base if keep else None}
    if scn.get("level") == "L4" and ok and os.path.isdir(os.path.join(own, "skills")):
        out = os.path.join(ROOT, "evals", "results", f"{time.strftime('%Y%m%d-%H%M%S')}-{scn['name']}-content")
        shutil.copytree(own, out, ignore=IGNORE)
        summary["content_saved_to"] = os.path.relpath(out, ROOT)
    if not keep:
        shutil.rmtree(base, ignore_errors=True)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenarios", nargs="*")
    ap.add_argument("--stack", help="run this stack repo's evals/scenarios/ with it loaded")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--budget", type=float, default=8.0, help="max USD per phase")
    ap.add_argument("--keep", action="store_true", help="keep the throwaway run directories")
    a = ap.parse_args()
    stack = os.path.realpath(a.stack) if a.stack else None
    if stack and not a.scenarios:
        d = os.path.join(stack, "evals", "scenarios")
        a.scenarios = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".yaml")) if os.path.isdir(d) else []
    if not a.scenarios:
        ap.error("no scenarios")
    os.makedirs(os.path.join(ROOT, "evals", "results"), exist_ok=True)
    allp = []
    for s in a.scenarios:
        passed = 0
        for i in range(a.runs):
            r = run_scenario(s, a.model, a.budget, a.keep, stack)
            passed += r["passed"]
            with open(os.path.join(ROOT, "evals", "results", f"{time.strftime('%Y%m%d-%H%M%S')}-{r['scenario']}.json"), "w") as f:
                json.dump(r, f, indent=1)
            bad = [c for ph in r["phases"] for c in ph["checks"] if not c["ok"]]
            print(f"{'PASS' if r['passed'] else 'FAIL'} {r['scenario']} run {i + 1}/{a.runs}: {r['seconds']}s, "
                  f"${r['cost_usd']}" + (f" (kept: {r['workdir']})" if r["workdir"] else "")
                  + "".join(f"\n     x {c['name']}: {c['detail']}" for c in bad), flush=True)
        allp.append((os.path.basename(s), passed, a.runs))
    print("\npass rates:")
    for n, p, t in allp:
        print(f"  {n}: {p}/{t}")
    return 0 if all(p == t for _, p, t in allp) else 1


if __name__ == "__main__":
    sys.exit(main())
