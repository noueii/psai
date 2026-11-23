#!/usr/bin/env python3
"""Maintainer checks for a skills repo: psai itself, or a stack (the same layout). Never shipped to users.

Usage: check.py [<repo>] [--upstream] [--with <repo> ...]
  <repo>      the repo to check (default: this psai clone)
  --with      another repo whose skills `skill:path` refs may name (e.g. a stack this one builds on)
  --upstream  psai itself: also fail if it ships content (a workflow, a rules or shared skill, knowledge/)
A stack's skills must all start with its name (`<stack>-`, or `workflow-<stack>-` for a workflow).

Checks: every SKILL.md's frontmatter (the closed Agent Skills field set, name == folder, a quoted description with
"Use when", at most 1024 characters, never disable-model-invocation); skills/ is flat; the manifests parse and
agree on name and version; every folder outside skills/ has a README.md; every workflow skill's refs, graph rules
(reachable, can end, loops limited) and simulator cases (evals/cases/<workflow skill>.yaml).
Needs python3 with PyYAML.
"""
import json
import os
import re
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import workflows  # noqa: E402

SKILL_FIELDS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".claude-plugin", ".github"}


class Report:
    def __init__(self):
        self.fails = 0

    def ok(self, msg):
        print(f"  ok   {msg}")

    def fail(self, msg):
        print(f"  FAIL {msg}")
        self.fails += 1

    def check(self, cond, msg, detail=""):
        if cond:
            self.ok(msg)
        else:
            self.fail(msg + (f": {detail}" if detail else ""))
        return cond


def frontmatter(path):
    """(raw frontmatter text, parsed dict) or (None, None)."""
    text = open(path, encoding="utf-8").read()
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return None, None
    return m.group(1), yaml.safe_load(m.group(1)) or {}


def skill_dirs(repo):
    base = os.path.join(repo, "skills")
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base) if os.path.isfile(os.path.join(base, d, "SKILL.md")))


def check_skills(repo, r):
    print("skills")
    names = skill_dirs(repo)
    for d in names:
        p = os.path.join(repo, "skills", d, "SKILL.md")
        try:
            raw, fm = frontmatter(p)
        except yaml.YAMLError as e:
            r.fail(f"{d}: frontmatter doesn't parse ({str(e).splitlines()[0]})")
            continue
        if fm is None:
            r.fail(f"{d}: no frontmatter")
            continue
        problems = []
        extra = sorted(set(fm) - SKILL_FIELDS)
        if extra:
            problems.append(f"fields outside the Agent Skills set: {', '.join(extra)}")
        if fm.get("name") != d:
            problems.append(f"name {fm.get('name')!r} != folder")
        desc = fm.get("description")
        if not isinstance(desc, str) or not desc.strip():
            problems.append("no description")
        else:
            if len(desc) > 1024:
                problems.append(f"description is {len(desc)} characters (max 1024)")
            if "Use when" not in desc:
                problems.append('description has no "Use when"')
            if not re.search(r'^description:\s*"', raw, re.M):
                problems.append("description isn't quoted")
        r.check(not problems, f"{d}: frontmatter", "; ".join(problems))
    nested = []
    for root, dirs, files in os.walk(os.path.join(repo, "skills")):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        depth = os.path.relpath(root, os.path.join(repo, "skills")).count(os.sep)
        if "SKILL.md" in files and depth >= 1:
            nested.append(os.path.relpath(os.path.join(root, "SKILL.md"), repo))
    r.check(not nested, "skills/ is flat (no SKILL.md below skills/<name>/)", ", ".join(nested))
    return names


def load_json(repo, rel, r):
    p = os.path.join(repo, rel)
    if not os.path.isfile(p):
        r.fail(f"{rel} is missing")
        return None
    try:
        return json.load(open(p))
    except ValueError as e:
        r.fail(f"{rel} doesn't parse: {e}")
        return None


def check_manifests(repo, r):
    print("manifests")
    claude = load_json(repo, ".claude-plugin/plugin.json", r)
    market = load_json(repo, ".claude-plugin/marketplace.json", r)
    agent = load_json(repo, "plugin.json", r)
    pkg = load_json(repo, "package.json", r)
    if not all((claude, market, agent, pkg)):
        return None
    name, version = claude.get("name"), claude.get("version")
    r.check(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", name or "") and "--" not in name,
            f"plugin name {name!r} is lowercase letters, digits and single hyphens")
    r.check(re.fullmatch(r"\d+\.\d+\.\d+", str(version)), f"version {version!r} is semver")
    r.check(agent.get("$schema") == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "plugin.json targets Agent Plugins 1.0.0")
    allowed = {"$schema", "name", "version", "description", "author", "homepage", "repository", "license", "keywords",
               "extensions"}
    r.check(not set(agent) - allowed, "plugin.json has only Agent Plugins fields", ", ".join(sorted(set(agent) - allowed)))
    same = {"plugin.json": (agent.get("name"), agent.get("version")), "package.json": (pkg.get("name"), pkg.get("version"))}
    bad = [f"{k} has {v}" for k, v in same.items() if v != (name, version)]
    r.check(not bad, f"every manifest says {name} {version}", "; ".join(bad))
    plugins = [p.get("name") for p in market.get("plugins", [])]
    r.check(plugins == [name] and market["plugins"][0].get("source") == "./",
            "marketplace.json lists this one plugin with source ./", str(plugins))
    pi = pkg.get("pi") or {}
    r.check("./skills" in (pi.get("skills") or []), 'package.json "pi" ships ./skills')
    for ext in pi.get("extensions") or []:
        r.check(os.path.isfile(os.path.join(repo, ext)), f"pi extension {ext} exists")
    hooks = os.path.join(repo, "hooks", "hooks.json")
    if os.path.isfile(hooks):
        text = open(hooks).read()
        for ref in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"\\ ]+)", text):
            r.check(os.path.isfile(os.path.join(repo, ref)), f"hooks.json names {ref}, which exists")
    return name


def check_names(names, stack, r):
    print("names")
    bad = [n for n in names if not (n.startswith(f"{stack}-") or n.startswith(f"workflow-{stack}-"))]
    r.check(not bad, f"every skill starts with {stack}- or workflow-{stack}-", ", ".join(bad))


def check_workflows(repo, extra, r):
    names = [n for n in workflows.skills_in([repo]) if n.startswith("workflow-")]
    if not names:
        return
    print("workflows")
    skills = workflows.skills_in([repo] + extra)
    refs = workflows.Refs(skills)
    for n in names:
        errs = workflows.validate(skills[n], refs, skills)
        r.check(not errs, f"{n}: refs resolve, every node reachable and able to end, every loop limited",
                "; ".join(errs))
        if not errs:
            for case, ok, detail in workflows.simulate(repo, skills[n]):
                r.check(ok, f"simulate {case}", detail)
    if refs.external:
        print(f"  note not checked (skills outside this repo; add --with <repo>): {', '.join(sorted(refs.external))}")


def check_readmes(repo, r):
    print("structure")
    missing = []
    for root, dirs, files in os.walk(repo):
        rel = os.path.relpath(root, repo)
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not (rel == "skills") and
                         not (rel == "evals" and x == "results"))
        if rel.startswith("evals" + os.sep + "fixtures" + os.sep):
            dirs[:] = []
            continue
        if "README.md" not in files and rel != ".":
            missing.append(rel)
    r.check(not missing, "every folder outside skills/<name>/ has a README.md", ", ".join(missing))


def check_upstream(repo, names, r):
    print("upstream (psai ships no content)")
    content = [n for n in names if n.startswith("workflow-") or n.endswith("-rules") or n.endswith("-shared")]
    r.check(not content, "no workflow, rules or shared skill", ", ".join(content))
    r.check(not os.path.exists(os.path.join(repo, "knowledge")), "no knowledge/ folder")
    nudge = os.path.join(repo, "skills", "request-router", "nudge.md")
    words = len(open(nudge).read().split()) if os.path.isfile(nudge) else 0
    r.check(0 < words <= 120, f"the nudge (request-router/nudge.md) has {words} words, at most 120")


def main(argv):
    here = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    args, extra, i = [], [], 0
    while i < len(argv):
        if argv[i] == "--with":
            extra.append(os.path.realpath(argv[i + 1]))
            i += 1
        elif not argv[i].startswith("--"):
            args.append(argv[i])
        i += 1
    repo = os.path.realpath(args[0] if args else here)
    r = Report()
    names = check_skills(repo, r)
    stack = check_manifests(repo, r)
    check_workflows(repo, extra, r)
    check_readmes(repo, r)
    if "--upstream" in argv:
        r.check(names, "skills/ holds at least one skill")
        check_upstream(repo, names, r)
    elif stack and stack != "psai":
        check_names(names, stack, r)
    return r.fails


if __name__ == "__main__":
    fails = main(sys.argv[1:])
    print(f"check.py: {'all passed' if not fails else f'{fails} failed'}")
    sys.exit(1 if fails else 0)
