#!/usr/bin/env python3
"""psai: the one command. install.sh links it as ~/.local/bin/psai ($PSAI_BIN overrides the folder).

  psai install [--dry-run|--uninstall]   run install.sh
  psai update [--force]                   fast-forward your overlay (keeps inbox entries) and the framework, re-install
  psai status                             one screen: version, install, pending retro, unsynced, staged, drift, last sync
  psai doctor                             status, plus per tool: version, plugin loaded, skills missing or unmanaged
  psai sync [run|check|update|drift|baseline|stage|pr|migrate]   see scripts/sync.py (the sync skill drives it)
  psai stage [<stack>]                    print (and create) a target's stage worktree: your overlay, or a dev stack
  psai retro [gather|finish|suggest]      see scripts/retro.py (the retro skill drives it)
  psai adopt <skill> [--to <dev stack>]   bring an unmanaged skill into your overlay (or a stack you author)
  psai skills [list|check|brief|...]      the live skill registry
  psai ledger [list|show|...]             the local session ledger
  psai check [<stack>|<path>] [--quick]   L0 + L2 for one stack (with your overrides), or every installed stack;
                                          psai check --framework [args] runs psai's own tests (scripts/check.sh)
  psai new-stack <name> [--dir D]         start a stack from template/stack (a git repo), added as a dev stack
  psai build --standalone [<stack>] [--target claude] [--out D] [--check]   native packages, no psai install needed
  psai eval <stack|path> [scenario...] [--tool T] [--runs N]   the stack's AI evals in a temp home
  psai stack add|remove|update|list|sync|diff ...   install and manage stacks (scripts/stacks.py)
  psai resolve model <stack>:<role> [--tool T]   the role's model for a tool (scripts/models.py)
  psai setup models [--set <tool>.<tier>=<id>]  write your overlay's tier map (fast | balanced | strong per tool)
  psai resolve [kind] <ref> [--from S] [--all] [--json] [--write]   find content by name (scripts/resolve.py)
  psai context | role-context [home] [shown]   the injected nudge (harness.py context)
  psai graph | simulate [<stack>|<path>] [args]   graph.py, simulate.py (a stack name or folder; default the home)
  psai route | index                      the merged routing index (the request-router skill reads it) | rebuild it
  psai node <workflow> <node>             a node's resolved files and skills (the work skill reads it)
  psai trace <workflow> <node>            record a move; refuse one that isn't an edge (skills/work/trace.sh)
  psai check-diff <workflow> <node> <base>   check a role's diff against its may_change (skills/work/check-diff.sh)
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import ledger  # noqa: E402
import skills as skillreg  # noqa: E402
import sync  # noqa: E402

REPO = os.path.dirname(HERE)
TOOLS = ["claude", "opencode", "pi", "omp"]


def root():
    """The home ($PSAI_HOME or ~/.psai): a stacks-layout home (framework/, overlay/, stacks/, state/), a single-root
    clone, or (neither) this clone."""
    r = ledger.root_dir()
    if os.path.isdir(os.path.join(r, "framework")) or os.path.exists(os.path.join(r, "scripts", "harness.py")):
        return r
    return REPO


def run(cmd):
    return subprocess.run(cmd).returncode


def lines_status(r, fetch=False):
    fw = sync.framework_of(r)
    r = sync.root_of(r)
    out = []
    head = sync.rev(fw, "HEAD")
    br = sync.gv(fw, "rev-parse", "--abbrev-ref", "HEAD")
    out.append(f"psai {ledger.version(r)} at {fw} ({br})" + (f"; your overlay: {r}" if r != fw else ""))
    inst = sync.installed(r).get("commit")
    out.append(f"install: {'matches HEAD' if inst == head else ('never recorded' if not inst else f'{inst[:12]} != HEAD')}")
    if fetch:
        sync.fetch(r)
    t = sync.follow_ref(r)
    if t:
        n = sync.gv(r, "rev-list", "--count", f"HEAD..{t}")
        out.append(f"update: {n} new commit(s) on {t}" if n and n != "0" else f"update: none known on {t}"
                   + ("" if fetch else " (no fetch; `psai sync check` fetches)"))
    else:
        out.append("update: no remote branch to follow")
    recs = ledger.records(r)
    pend = [x["id"] for x in recs if x.get("end") and x.get("retro_pending")]
    uns = [x["id"] for x in recs if ledger.unsynced(x)]
    out.append(f"sessions: {len(recs)} recorded, {len([x for x in recs if not x.get('end')])} open, "
               f"{len(pend)} waiting for a retro, {len(uns)} unsynced")
    inbox = sum(ledger.inbox_counts(r).values())
    pend = sync.all_pending(r)
    _, skipped = sync.pending_changes(r)
    out.append(f"knowledge inbox: {inbox} entr{'y' if inbox == 1 else 'ies'}; staged or captured, not in a PR: "
               + (", ".join(f"{n} {len(c)} file(s)" for n, c in pend.items()) or "0 file(s)")
               + (f"; upstream-owned files edited locally: {len(skipped)}" if skipped else ""))
    h = ledger.home(r)
    if not h.compat:
        import resolve  # noqa: PLC0415
        import stacks  # noqa: PLC0415
        fwv = resolve.framework_version(h.framework)
        for e in stacks.entries(h):
            st = h.get(e.get("name"))
            meta = st.meta if st else {}
            rng = meta.get("psai", "")
            try:
                ok = resolve.in_range(fwv, rng) if rng else True
            except ValueError:
                ok = False
            dr = stacks.drifted(h, e.get("name")) if st and os.path.exists(st.path) else []
            out.append(f"stack {e.get('name')}: {meta.get('version', e.get('version', '?'))} at {e.get('ref') or e.get('mode')}"
                       f" ({e.get('mode', 'pinned')}); {'in range' if ok else 'needs psai ' + rng}"
                       + (f"; {len(dr)} override(s) changed upstream" if dr else ""))
    out.append(f"retro reports waiting for a PR: {len(sync.reports(r))}")
    mig = sync.pending_migrations(r)
    out.append(f"migrations pending: {', '.join(os.path.basename(m) for m in mig) or 'none'}")
    d = sync.drift(r)
    out.append("drift: " + (("no baseline yet (first sync records one)" if not d["baseline"] else "none since the last scan")
                            if not d["changed"] or not d["baseline"] else "; ".join(d["changed"])))
    s = ledger.read_json(sync.st(r, "sync.json"), {}) or {}
    out.append(f"last sync: {s.get('last_sync', 'never')}; last PR branch: {s.get('last_pr', 'none')}")
    return out


def tool_version(t):
    exe = shutil.which(t)
    if not exe:
        return None
    try:
        p = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
        return (p.stdout or p.stderr).strip().splitlines()[0][:60] if (p.stdout or p.stderr).strip() else "?"
    except (subprocess.TimeoutExpired, OSError, IndexError):
        return "?"


def plugin_loaded(t, r, home):
    cfg = skillreg._cfg(home)
    link = ledger.root_dir()
    r = sync.framework_of(r)
    if t == "claude":
        s = ledger.read_json(os.path.join(home, ".claude", "settings.json"), {}) or {}
        src = ((s.get("extraKnownMarketplaces") or {}).get("psai") or {}).get("source") or {}
        on = (s.get("enabledPlugins") or {}).get("psai@psai") is True
        return on and os.path.realpath(src.get("path", "")) == os.path.realpath(r), "psai@psai " + ("enabled" if on else "not enabled")
    if t in ("pi", "omp"):
        p = os.path.join(home, f".{t}", "agent", "extensions", "psai.ts")
        ok = os.path.islink(p) and os.path.realpath(p) == os.path.realpath(os.path.join(r, "plugins", t, "psai.ts"))
        return ok, f"{p} {'linked' if ok else 'missing'}"
    p = os.path.join(cfg, "opencode", "plugin", "psai.js")
    ok = os.path.exists(p) and (link in open(p).read() or r in open(p).read())
    return ok, f"{p} {'present' if ok else 'missing'}"


def present(t, home):
    cfg = skillreg._cfg(home)
    return os.path.isdir({"claude": os.path.join(home, ".claude"), "opencode": os.path.join(cfg, "opencode"),
                          "pi": os.path.join(home, ".pi", "agent"), "omp": os.path.join(home, ".omp", "agent")}[t])


def doctor(r):
    r = sync.root_of(r)
    home = os.path.expanduser("~")
    out = lines_status(r, fetch=True)
    try:
        idx = skillreg.registry(r, project=skillreg.project_root())
    except Exception as e:  # noqa: BLE001
        idx = {}
        out.append(f"skills: registry failed: {e}")
    managed = [n for n, s in idx.items() if any(loc["kind"] in ("psai", "my-skills", "pack") for loc in s["locations"])]
    out.append("")
    for t in TOOLS:
        if not present(t, home):
            out.append(f"{t}: not installed here (no config folder)")
            continue
        ok, how = plugin_loaded(t, r, home)
        missing = sorted(n for n in managed if t not in idx[n]["tools"])
        unmanaged = sorted(n for n, s in idx.items() if s["unmanaged"] and t in s["tools"])
        out += [f"{t}: {tool_version(t) or 'binary not on PATH'}",
                f"  plugin: {'ok' if ok else 'NOT LOADED'} ({how})",
                f"  psai skills it can't see: {', '.join(missing) or 'none'}",
                f"  unmanaged skills it sees: {', '.join(unmanaged) or 'none'}"]
    return out


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd, rest = argv[0], argv[1:]
    r = root()
    py = [sys.executable]
    if cmd == "install":
        return run(["bash", os.path.join(REPO, "install.sh"), *rest])
    if cmd == "adopt":  # into your overlay, or --to <dev stack>; then relink
        rc = run(py + [os.path.join(HERE, "harness.py"), "skills", "adopt", *rest])
        return rc if rc or "--dry-run" in rest else run(["bash", os.path.join(REPO, "install.sh"), "--relink"])
    if cmd == "update":
        return sync.main(["update", *rest])
    if cmd == "sync":
        return sync.main(rest)
    if cmd == "stage":  # psai stage [<stack>]: a target's stage worktree (your overlay by default)
        return sync.main(["stage", "--stack", rest[0]] if rest else ["stage"])
    if cmd == "retro":
        import retro  # noqa: PLC0415
        return retro.main(rest)
    if cmd == "stack":
        import stacks  # noqa: PLC0415
        return stacks.stack_main(rest)
    if cmd == "resolve" and rest[:1] == ["model"]:
        import models  # noqa: PLC0415
        return models.main(rest[1:])
    if cmd == "resolve":
        import resolve  # noqa: PLC0415
        return resolve.main(rest)
    if cmd == "setup":
        import models  # noqa: PLC0415
        return models.setup_main(rest)
    if cmd == "ledger":
        return ledger.main(rest)
    if cmd == "skills":
        return run(py + [os.path.join(HERE, "harness.py"), "skills", *rest])
    if cmd == "check":
        import stacks  # noqa: PLC0415
        return stacks.check_main(rest)
    if cmd == "new-stack":
        import argparse  # noqa: PLC0415
        import stacks  # noqa: PLC0415
        ap = argparse.ArgumentParser(prog="psai new-stack")
        ap.add_argument("name")
        ap.add_argument("--dir", help="where to create it (default ./<name>)")
        ap.add_argument("--description")
        ap.add_argument("--no-add", action="store_true", help="don't add it as a dev stack")
        a = ap.parse_args(rest)
        try:
            return stacks.new_stack(a.name, a.dir, a.description, not a.no_add)
        except stacks.StackError as e:
            print(f"psai new-stack: {e}", file=sys.stderr)
            return 1
    if cmd == "build":
        import build  # noqa: PLC0415
        return build.main(rest)
    if cmd == "eval":
        return run(["bash", os.path.join(REPO, "evals", "run.sh"), "--stack", *rest])
    if cmd in ("context", "role-context"):
        return run(py + [os.path.join(HERE, "harness.py"), cmd, *(rest or [r])])
    if cmd in ("graph", "simulate"):
        args = rest if rest and not rest[0].startswith("-") else [r, *rest]
        import harness  # noqa: PLC0415
        args[0] = harness.stack_root(args[0])
        return run(py + [os.path.join(HERE, f"{cmd}.py"), *args])
    if cmd in ("route", "index", "node", "trace", "check-diff"):
        import engine  # noqa: PLC0415
        return engine.main(cmd, rest)
    if cmd == "status":
        print("\n".join(lines_status(r)))
        return 0
    if cmd == "doctor":
        print("\n".join(doctor(r)))
        return 0
    print(f"psai: unknown command {cmd!r}; see `psai --help`", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
