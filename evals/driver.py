#!/usr/bin/env python3
"""Run eval scenarios headless against a tool, with a scripted fake owner. Called by evals/run.sh.

Each run gets a throwaway directory:
- harness/   a copy of this harness (vanilla), with the scenario's test content overlaid; HARNESS_HOME points here;
- work/      a copy of the fixture repo, a git repo whose origin is remote.git (a local bare repo);
- bin/gh     a shim that logs and refuses, so nothing reaches GitHub;
- trace.log  check-diff.sh's lines (HARNESS_TRACE).

The real HOME is only read in place by the tool for its own login. Nothing is copied from it and no harness file
is installed into it.
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
import grade  # noqa: E402

BLOCK = re.compile(r"<<<HARNESS\s*\n(.*?)\n\s*>>>", re.S)
IGNORE = shutil.ignore_patterns(".git", "results", "__pycache__")


def sh(cmd, cwd, env=None, check=True):
    return subprocess.run(cmd, cwd=cwd, env=env, shell=True, check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def git_init(path, msg="fixture"):
    sh("git init -q -b main && git add -A && git -c user.email=eval@local -c user.name=eval commit -qm "
       f"'{msg}'", path)


def prepare(scn, base):
    h, w = os.path.join(base, "harness"), os.path.join(base, "work")
    shutil.copytree(ROOT, h, ignore=IGNORE, symlinks=True)
    if scn.get("content"):
        src = os.path.join(ROOT, "evals", "fixtures", scn["content"])
        shutil.copytree(src, h, dirs_exist_ok=True, ignore=shutil.ignore_patterns("README.md"))
    git_init(h, "harness")
    shutil.copytree(os.path.join(ROOT, "evals", "fixtures", scn["fixture"]), w, ignore=IGNORE)
    git_init(w)
    sh(f"git init -q --bare {base}/remote.git && git remote add origin {base}/remote.git && git push -q origin main", w)
    b = os.path.join(base, "bin")
    os.makedirs(b)
    with open(os.path.join(b, "gh"), "w") as f:
        f.write(f'#!/bin/sh\necho "gh $*" >> {base}/gh.log\necho "gh is disabled in evals" >&2\nexit 1\n')
    os.chmod(os.path.join(b, "gh"), 0o755)
    return h, w


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
    kind, q = block.get("kind", "escalation"), block.get("question", "") + " " + block.get("why", "")
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


# ---------- tool adapters ----------
class Claude:
    name = "claude"

    def __init__(self, h, cwd, env, model, budget):
        self.p = subprocess.Popen(
            ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
             "--plugin-dir", h, "--setting-sources", "project", "--no-session-persistence", "--strict-mcp-config",
             "--permission-mode", "bypassPermissions", "--append-system-prompt-file", os.path.join(h, "instructions", "global.md"),
             "--add-dir", h, "--model", model, "--max-budget-usd", str(budget)],
            cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.texts, self.cost = [], 0.0

    def turn(self, message):
        self.p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": message}}) + "\n")
        self.p.stdin.flush()
        for line in self.p.stdout:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "assistant" and not d.get("parent_tool_use_id"):
                for c in d["message"].get("content", []):
                    if c.get("type") == "text":
                        self.texts.append(c["text"])
            if d.get("type") == "result":
                self.cost = d.get("total_cost_usd") or self.cost
                return d.get("result") or ""
        return None

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=30)
        except Exception:
            self.p.kill()


class Omp:
    name = "omp"

    def __init__(self, h, cwd, env, model, budget):
        cfg = os.path.join(os.path.dirname(h), "omp-config.yml")
        with open(cfg, "w") as f:
            yaml.safe_dump({"skills": {"customDirectories": [os.path.join(h, "skills")], "enableAgentsUser": False,
                                       "enableClaudeUser": False, "enableCodexUser": False, "enablePiUser": False,
                                       "enableAgentsProject": False, "enableClaudeProject": False,
                                       "enablePiProject": False}}, f)
        args = ["omp", "--mode", "rpc", "--no-session", "--no-title", "--config", cfg,
                "--append-system-prompt", os.path.join(h, "instructions", "global.md")]
        self.p = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True)
        self.texts, self.cost, self.n = [], 0.0, 0

    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()

    def _wait(self, pred):
        for line in self.p.stdout:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "message_end":
                m = d.get("message") or {}
                if m.get("role") == "assistant":
                    for c in m.get("content", []) or []:
                        if isinstance(c, dict) and c.get("type") == "text":
                            self.texts.append(c.get("text", ""))
            if pred(d):
                return d
        return None

    def turn(self, message):
        self._send({"type": "prompt", "message": message})
        if self._wait(lambda d: d.get("type") == "agent_end") is None:
            return None
        self.n += 1
        self._send({"id": f"t{self.n}", "type": "get_last_assistant_text"})
        r = self._wait(lambda d: d.get("type") == "response" and d.get("id") == f"t{self.n}")
        self._send({"id": f"s{self.n}", "type": "get_session_stats"})
        s = self._wait(lambda d: d.get("type") == "response" and d.get("id") == f"s{self.n}")
        try:
            self.cost = float(((s or {}).get("data") or {}).get("cost") or (((s or {}).get("data") or {}).get("tokens") or {}).get("cost") or 0)
        except (TypeError, ValueError):
            pass
        data = (r or {}).get("data")
        return data.get("text", "") if isinstance(data, dict) else (data or "")

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=30)
        except Exception:
            self.p.kill()


TOOLS = {"claude": Claude, "omp": Omp}


def run_phase(tool, phase, h, w, base, model, budget):
    cwd = h if phase.get("cwd") == "harness" else w
    env = dict(os.environ, HARNESS_HOME=h, HARNESS_TRACE=os.path.join(base, "trace.log"),
               PATH=os.path.join(base, "bin") + os.pathsep + os.environ["PATH"])
    owner = phase.get("owner") or {}
    log = {"reviews": 0, "questions": 0, "escalations": [], "unexpected": [], "turns": 0}
    agent = TOOLS[tool](h, cwd, env, model, budget)
    msg = phase["task"]
    final = ""
    t0 = time.time()
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
    log.update(seconds=round(time.time() - t0), cost=round(agent.cost, 4), final=final,
               path=re.findall(r"\[harness\] node: ([A-Za-z0-9_-]+)", text), cwd=cwd)
    return log


def run_scenario(path, tool, model, budget, keep):
    scn = yaml.safe_load(open(path))
    phases = scn.get("phases") or [{k: scn[k] for k in ("task", "owner", "expect") if k in scn}]
    base = tempfile.mkdtemp(prefix=f"psai-eval-{scn['name']}-")
    h, w = prepare(scn, base)
    refs0 = remote_refs(base)
    head0 = sh("git rev-parse HEAD", w).stdout.strip()
    results, ok = [], True
    for ph in phases:
        log = run_phase(tool, ph, h, w, base, model, budget)
        checks = grade.grade(ph.get("expect") or {}, log, dict(base=base, harness=h, work=w, refs0=refs0, head0=head0,
                                                            remote_refs=remote_refs(base)))
        ok = ok and all(c[1] for c in checks)
        results.append({"phase": ph.get("name", "main"), "seconds": log["seconds"], "cost_usd": log["cost"],
                        "turns": log["turns"], "path": log["path"], "escalations": log["escalations"],
                        "questions": log["questions"], "reviews": log["reviews"], "unexpected": log["unexpected"],
                        "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]})
        if not ok:
            break
        br = [b for b in sh("git branch --format='%(refname:short)'", h).stdout.split() if b.startswith("customize/")]
        if br:  # later phases run on what customize-harness built
            sh(f"git checkout -q {br[0]}", h, check=False)
    summary = {"scenario": scn["name"], "level": scn.get("level"), "tool": tool, "model": model, "passed": ok,
               "seconds": sum(r["seconds"] for r in results), "cost_usd": round(sum(r["cost_usd"] for r in results), 4),
               "phases": results, "workdir": base if keep else None}
    if scn.get("level") == "L4" and ok:
        out = os.path.join(ROOT, "evals", "results", f"{time.strftime('%Y%m%d-%H%M%S')}-{scn['name']}-{tool}-content")
        for d in ("workflows", "steps", "roles", "guides", "templates", "instructions", "knowledge"):
            if os.path.isdir(os.path.join(h, d)):
                shutil.copytree(os.path.join(h, d), os.path.join(out, d), ignore=IGNORE)
        summary["content_saved_to"] = os.path.relpath(out, ROOT)
    if not keep:
        shutil.rmtree(base, ignore_errors=True)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenarios", nargs="+")
    ap.add_argument("--tool", default="claude", choices=sorted(TOOLS))
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--budget", type=float, default=8.0, help="max USD per phase (Claude Code)")
    ap.add_argument("--keep", action="store_true", help="keep the throwaway run directories")
    a = ap.parse_args()
    os.makedirs(os.path.join(ROOT, "evals", "results"), exist_ok=True)
    allp = []
    for s in a.scenarios:
        passed = 0
        for i in range(a.runs):
            r = run_scenario(s, a.tool, a.model, a.budget, a.keep)
            passed += r["passed"]
            stamp = time.strftime("%Y%m%d-%H%M%S")
            with open(os.path.join(ROOT, "evals", "results", f"{stamp}-{r['scenario']}-{a.tool}.json"), "w") as f:
                json.dump(r, f, indent=1)
            bad = [c for ph in r["phases"] for c in ph["checks"] if not c["ok"]]
            print(f"{'PASS' if r['passed'] else 'FAIL'} {r['scenario']} [{a.tool}] run {i + 1}/{a.runs}: "
                  f"{r['seconds']}s, ${r['cost_usd']}" + "".join(f"\n     x {c['name']}: {c['detail']}" for c in bad))
        allp.append((os.path.basename(s), passed, a.runs))
    print("\npass rates:")
    for n, p, t in allp:
        print(f"  {n}: {p}/{t}")
    return 0 if all(p == t for _, p, t in allp) else 1


if __name__ == "__main__":
    sys.exit(main())
