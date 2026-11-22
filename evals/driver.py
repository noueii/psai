#!/usr/bin/env python3
"""Run eval scenarios headless against a tool, with a scripted fake owner. Called by evals/run.sh.

Each run gets a throwaway directory:
- harness/   a copy of this harness (vanilla), with the scenario's test content overlaid; PSAI_HOME points here;
- home/      with `stacks:` in the scenario, a stacks-layout home instead (ADR 0011): framework/ links harness/,
             stacks/<name>/ are copies of the listed fixtures, overlay/ is `overlay:` (or an empty overlay), and
             PSAI_HOME points here;
- work/      a copy of the fixture repo, a git repo whose origin is remote.git (a local bare repo);
- bin/gh     a shim that logs and refuses, so nothing reaches GitHub; bin/psai runs the copy's psai command;
- trace.log  check-diff.sh's lines (PSAI_TRACE).

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
IGNORE = shutil.ignore_patterns(".git", "results", "__pycache__", ".state", ".skills-cache")


def sh(cmd, cwd, env=None, check=True):
    return subprocess.run(cmd, cwd=cwd, env=env, shell=True, check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def git_init(path, msg="fixture"):
    sh("git init -q -b main && git add -A && git -c user.email=eval@local -c user.name=eval commit -qm "
       f"'{msg}'", path)


def prepare(scn, base):
    h, w = os.path.join(base, "harness"), os.path.join(base, "work")
    shutil.copytree(ROOT, h, ignore=IGNORE, symlinks=True)
    for rel in ("evals/scenarios/psai", "evals/graders"):  # the agent must not see the expected answers
        shutil.rmtree(os.path.join(h, rel), ignore_errors=True)
    content = scn.get("content")
    for c in [content] if isinstance(content, str) else (content or []):  # overlays, in order
        src = os.path.join(ROOT, "evals", "fixtures", c)
        shutil.copytree(src, h, dirs_exist_ok=True, ignore=shutil.ignore_patterns("README.md"))
    for rel in scn.get("strip") or []:  # e.g. hide the test content from a bootstrap run
        shutil.rmtree(os.path.join(h, rel), ignore_errors=True)
    git_init(h, "harness")
    home = stacks_home(scn, base, h) if scn.get("stacks") else h
    # this machine's state for the copy: installed at HEAD, migrations done (never run against the real HOME), and a
    # drift baseline of the real HOME (read only), so sync has nothing to update or adopt unless the run creates it
    sh(f"python3 scripts/sync.py installed --record --root {home} && python3 scripts/sync.py baseline --root {home}", h)
    mig = {os.path.basename(m): "eval" for m in sorted(os.listdir(os.path.join(h, "migrations"))) if m.endswith(".sh")}
    state = os.path.join(home, "state" if home != h else ".state")
    with open(os.path.join(state, "migrations.json"), "w") as f:
        json.dump(mig, f)
    shutil.copytree(os.path.join(ROOT, "evals", "fixtures", scn["fixture"]), w, ignore=IGNORE)
    git_init(w)
    sh(f"git init -q --bare {base}/remote.git && git remote add origin {base}/remote.git && git push -q origin main", w)
    b = os.path.join(base, "bin")
    os.makedirs(b)
    with open(os.path.join(b, "gh"), "w") as f:
        f.write(f'#!/bin/sh\necho "gh $*" >> {base}/gh.log\necho "gh is disabled in evals" >&2\nexit 1\n')
    os.chmod(os.path.join(b, "gh"), 0o755)
    with open(os.path.join(b, "psai"), "w") as f:
        f.write(f'#!/bin/sh\nexec python3 {h}/scripts/psai.py "$@"\n')
    os.chmod(os.path.join(b, "psai"), 0o755)
    return h, w, home


def stacks_home(scn, base, h):
    """A stacks-layout home for the run: framework/ -> the harness copy, the scenario's stacks, an overlay."""
    home = os.path.join(base, "home")
    os.makedirs(os.path.join(home, "stacks"))
    os.symlink(h, os.path.join(home, "framework"))
    ents = []
    for name, fx in scn["stacks"].items():
        shutil.copytree(os.path.join(ROOT, "evals", "fixtures", fx), os.path.join(home, "stacks", name), ignore=IGNORE)
        ents.append({"name": name, "source": f"fixture:{fx}", "ref": "v0.0.0", "mode": "pinned"})
    ov = os.path.join(home, "overlay")
    if scn.get("overlay"):
        shutil.copytree(os.path.join(ROOT, "evals", "fixtures", scn["overlay"]), ov, ignore=IGNORE)
    else:
        sys.path.insert(0, os.path.join(h, "scripts"))
        import stacks  # noqa: PLC0415
        stacks.init_overlay(home)
    with open(os.path.join(ov, "stacks.yaml"), "w") as f:
        yaml.safe_dump({"stacks": ents}, f, sort_keys=False)
    if not os.path.isdir(os.path.join(ov, ".git")):
        git_init(ov, "overlay")
    os.makedirs(os.path.join(home, "state"), exist_ok=True)
    return home


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
        # The psai plugin (its SessionStart hook injects the nudge), plus a throwaway plugin that exposes the
        # harness skills the way ~/.claude/skills does in a real install.
        sp = os.path.join(os.path.dirname(h), "skills-plugin")
        os.makedirs(os.path.join(sp, ".claude-plugin"), exist_ok=True)
        with open(os.path.join(sp, ".claude-plugin", "plugin.json"), "w") as f:
            json.dump({"name": "harness-skills", "version": "0.0.0", "description": "eval-only skills link"}, f)
        sk = os.path.join(sp, "skills")  # psai's skills and my-skills/, as install.sh links them
        os.makedirs(sk, exist_ok=True)
        if env["PSAI_HOME"] != h:  # a stacks-layout home: the framework's, the overlay's and each stack's skills
            sys.path.insert(0, os.path.join(h, "scripts"))
            import stacks  # noqa: PLC0415
            for n, target in stacks.skill_sources(env["PSAI_HOME"]):
                os.symlink(target, os.path.join(sk, n))
        for sub in ("skills", "my-skills") if env["PSAI_HOME"] == h else ():
            d = os.path.join(h, sub)
            for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
                if os.path.isfile(os.path.join(d, n, "SKILL.md")) and not os.path.lexists(os.path.join(sk, n)):
                    os.symlink(os.path.join(d, n), os.path.join(sk, n))
        self.p = subprocess.Popen(
            ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
             "--plugin-dir", os.path.join(h, "plugins", "claude"), "--plugin-dir", sp,
             "--setting-sources", "project", "--no-session-persistence", "--strict-mcp-config",
             "--permission-mode", "bypassPermissions", "--add-dir", h, "--add-dir", env["PSAI_HOME"], "--model", model, "--max-budget-usd", str(budget)],
            cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.texts, self.sub_calls, self.cost = [], [], 0.0
        self.raw = open(os.path.join(os.path.dirname(h), "stream.jsonl"), "a")

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
            elif c.get("type") == "tool_use":  # agents often print [harness] lines with echo
                self.texts.append(json.dumps(c.get("input", {})).replace("\\n", "\n"))

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


class Omp:
    name = "omp"

    def __init__(self, h, cwd, env, model, budget):
        cfg = os.path.join(os.path.dirname(h), "omp-config.yml")
        with open(cfg, "w") as f:
            yaml.safe_dump({"skills": {"customDirectories": [os.path.join(h, "skills"), os.path.join(h, "my-skills")], "enableAgentsUser": False,
                                       "enableClaudeUser": False, "enableCodexUser": False, "enablePiUser": False,
                                       "enableAgentsProject": False, "enableClaudeProject": False,
                                       "enablePiProject": False}}, f)
        args = ["omp", "--mode", "rpc", "--no-session", "--no-title", "--config", cfg,
                "--extension", os.path.join(h, "plugins", "omp", "psai.ts")]
        self.p = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True)
        self.texts, self.cost, self.n = [], 0.0, 0
        self.raw = open(os.path.join(os.path.dirname(h), "stream.jsonl"), "a")

    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()

    def _wait(self, pred):
        for line in self.p.stdout:
            self.raw.write(line)
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
                        elif isinstance(c, dict) and c.get("type") not in ("thinking", "redacted_thinking"):
                            self.texts.append(json.dumps(c))  # tool calls, so graders see what was invoked
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


def run_phase(tool, phase, h, w, base, model, budget, home=None):
    cwd = h if phase.get("cwd") == "harness" else w
    env = dict(os.environ, PSAI_HOME=home or h, PSAI_TRACE=os.path.join(base, "trace.log"), PSAI_EVAL="1",
               PATH=os.path.join(base, "bin") + os.pathsep + os.environ["PATH"],
               GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@local", GIT_COMMITTER_NAME="eval",
               GIT_COMMITTER_EMAIL="eval@local")
    env.pop("PSAI_STATE", None)  # the copy's own .state
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
    log.update(seconds=round(time.time() - t0), cost=round(agent.cost, 4), final=final, text=text,
               sub_calls=getattr(agent, "sub_calls", None),
               path=re.findall(r"\[harness\] node: ([A-Za-z0-9_-]+)", text), cwd=cwd)
    return log


def use_staged(h):
    """customize-harness stages in the stage worktree; a retro may already have built a psai/ branch from it. Stand in
    for the owner merging it: put the staged files into the copy (uncommitted) or check out that branch, so grading
    and later phases see them. -> what was found: {stage: [files], branches: [psai/...], other: [non-psai branches]}"""
    sys.path.insert(0, os.path.join(h, "scripts"))
    import sync  # noqa: PLC0415
    staged = sync.stage_changes(h)
    brs = sh("git branch --format='%(refname:short)'", h).stdout.split()
    found = {"stage": sorted(staged), "branches": [b for b in brs if b.startswith("psai/")],
             "other": [b for b in brs if b != "main" and not b.startswith("psai/")]}
    for p, src in staged.items():
        dst = os.path.join(h, p)
        if src is None:
            if os.path.lexists(dst):
                os.remove(dst)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
    if not staged and found["branches"]:
        sh(f"git checkout -q {found['branches'][-1]}", h, check=False)
    return found


def run_scenario(path, tool, model, budget, keep):
    scn = yaml.safe_load(open(path))
    phases = scn.get("phases") or [{k: scn[k] for k in ("task", "owner", "expect") if k in scn}]
    base = tempfile.mkdtemp(prefix=f"psai-eval-{scn['name']}-")
    h, w, home = prepare(scn, base)
    refs0 = remote_refs(base)
    head0 = sh("git rev-parse HEAD", w).stdout.strip()
    results, ok = [], True
    for ph in phases:
        open(os.path.join(base, "trace.log"), "a").write(f"phase {ph.get('name', 'main')}\n")
        log = run_phase(tool, ph, h, w, base, model, budget, home)
        branches = sh("git branch --format='%(refname:short)'", h).stdout.split()
        found = use_staged(h) if ph.get("cwd") == "harness" else {}
        checks = grade.grade(ph.get("expect") or {}, log, dict(base=base, harness=h, work=w, refs0=refs0, head0=head0,
                                                            remote_refs=remote_refs(base), branches=branches, staged=found))
        ok = ok and all(c[1] for c in checks)
        tr = open(os.path.join(base, "trace.log")).read().split(f"phase {ph.get('name', 'main')}\n")[-1].splitlines()
        traced = [t.split()[1] for t in tr if t.startswith("node ")]
        results.append({"phase": ph.get("name", "main"), "seconds": log["seconds"], "cost_usd": log["cost"],
                        "turns": log["turns"], "path": traced or log["path"],
                        "role_checks": [t.replace("check-diff ", "") for t in tr if t.startswith("check-diff ")], "escalations": log["escalations"],
                        "questions": log["questions"], "reviews": log["reviews"], "unexpected": log["unexpected"],
                        "final_message": (log["final"] or "")[-1500:],
                        "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]})
        if not ok:
            break
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
