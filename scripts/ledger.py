#!/usr/bin/env python3
"""The session ledger: one local record per agent session, in <state>/sessions/<id>.json (git-ignored).

<state> is $PSAI_STATE, else the home's state/ (or <clone>/.state in a single-root home; the home is $PSAI_HOME or ~/.psai). A record holds: id, tool,
project, start, end, workflows run, escalations, retro done (or pending), captured counts (new inbox entries and
staged changes), drift seen, psai version, the installed stacks' versions, and the PR branch that synced it. The plugins write it at session start
and end; trace.sh (run by work) adds workflows and escalations; retro and sync mark it.

CLI (also `psai ledger ...`):
  ledger.py start --tool T --id ID [--project DIR] [--transcript FILE]
  ledger.py end [--id ID]
  ledger.py workflow <name> [--id ID] | escalation [--id ID]
  ledger.py list [--json] [--pending] [--unsynced]
Without --id, a command acts on the newest open session of this project (else the newest open session).
Every command is best-effort: a broken state folder never breaks a session.
"""
import datetime
import glob
import json
import os
import re
import subprocess
import sys


def root_dir(root=None):
    import resolve  # noqa: PLC0415
    return root or resolve.default_root()


def home(root=None):
    import resolve  # noqa: PLC0415
    return resolve.Home(root_dir(root))


def state_dir(root=None):
    return os.environ.get("PSAI_STATE") or home(root).state


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def git(root, *args, check=False):
    p = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout.strip() if p.returncode == 0 else ""


def version(root=None):
    import resolve  # noqa: PLC0415
    fw = home(root).framework
    sha = git(fw, "rev-parse", "--short", "HEAD") or "unknown"
    return f"{resolve.framework_version(fw)}+{sha}"


def stack_versions(root=None):
    """{stack: version} of the installed stacks (ADR 0011: a record holds the stacks it ran with)."""
    try:
        return {s.name: str(s.meta.get("version", "?")) for s in home(root).stacks}
    except Exception:  # noqa: BLE001 - the ledger is best-effort
        return {}


def project_of(path):
    path = os.path.abspath(path or os.getcwd())
    top = subprocess.run(["git", "-C", path, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return top.stdout.strip() if top.returncode == 0 else path


# ---------- what a session captured ----------
def inbox_files(root):
    """The overlay's inboxes: knowledge/inbox.md, knowledge/roles/<r>/inbox.md and knowledge/<stack>/roles/<r>/inbox.md."""
    r = home(root).overlay_path
    return sorted([os.path.join(r, "knowledge", "inbox.md")] + glob.glob(os.path.join(r, "knowledge", "roles", "*", "inbox.md"))
                  + glob.glob(os.path.join(r, "knowledge", "*", "roles", "*", "inbox.md")))


def inbox_counts(root=None):
    """{relative inbox path: number of `## ` entries}."""
    r = home(root).overlay_path
    out = {}
    for f in inbox_files(r):
        try:
            out[os.path.relpath(f, r)] = sum(1 for line in open(f) if line.startswith("## "))
        except OSError:
            pass
    return out


def path_id(sid):
    return re.sub(r"[^A-Za-z0-9._-]", "_", sid)[:120]


def rec_path(sid, root=None):
    return os.path.join(state_dir(root), "sessions", path_id(sid) + ".json")


def records(root=None):
    out = []
    for f in sorted(glob.glob(os.path.join(state_dir(root), "sessions", "*.json"))):
        r = read_json(f)
        if isinstance(r, dict) and r.get("id"):
            out.append(r)
    return sorted(out, key=lambda r: r.get("start", ""))


def current(root=None, sid=None, project=None):
    if sid:
        return read_json(rec_path(sid, root))
    recs = [r for r in records(root) if not r.get("end")]
    proj = project_of(project)
    mine = [r for r in recs if r.get("project") == proj]
    return (mine or recs or [None])[-1]


def save(rec, root=None):
    write_json(rec_path(rec["id"], root), rec)
    return rec


def needs_retro(rec):
    c = rec.get("captured") or {}
    return bool(rec.get("workflows") or c.get("inbox") or c.get("staged")) and not rec.get("retro")


def unsynced(rec):
    c = rec.get("captured") or {}
    return bool(c.get("inbox") or c.get("staged")) and not rec.get("synced")


def start(tool, sid, project=None, transcript=None, root=None):
    old = read_json(rec_path(sid, root))
    if old:  # resume, clear or compact: the same session goes on
        old.pop("end", None)
        old["resumed"] = old.get("resumed", 0) + 1
        return save(old, root)
    rec = {"id": sid, "tool": tool, "project": project_of(project), "start": now(), "workflows": [],
           "escalations": 0, "retro": False, "captured": {"inbox": 0, "staged": 0}, "drift": [],
           "psai_version": version(root), "stacks": stack_versions(root),
           "inbox_at_start": inbox_counts(root)}
    if transcript:
        rec["transcript"] = transcript
    return save(rec, root)


def captured(rec, root=None):
    """New inbox entries since the session started, and changes staged for a PR (stage worktree + live)."""
    base = rec.get("inbox_at_start") or {}
    new = sum(max(0, n - base.get(p, 0)) for p, n in inbox_counts(root).items())
    try:
        import sync  # noqa: PLC0415 - only for the staged count
        staged = len(sync.pending_changes(root_dir(root))[0])
    except Exception:  # noqa: BLE001
        staged = (rec.get("captured") or {}).get("staged", 0)
    return {"inbox": new, "staged": staged}


def end(sid=None, root=None):
    rec = current(root, sid)
    if not rec:
        return None
    rec["end"] = now()
    rec["captured"] = captured(rec, root)
    try:
        import sync  # noqa: PLC0415
        rec["drift"] = sorted(sync.drift(root_dir(root))["changed"])
    except Exception:  # noqa: BLE001
        pass
    rec["retro_pending"] = needs_retro(rec)
    return save(rec, root)


def update(sid=None, root=None, workflow=None, escalation=False, retro=None, synced=None):
    rec = current(root, sid)
    if not rec:
        return None
    if workflow:
        rec.setdefault("workflows", []).append(workflow)
    if escalation:
        rec["escalations"] = rec.get("escalations", 0) + 1
    if retro is not None:
        rec["retro"] = retro
        rec["retro_pending"] = False
    if synced:
        rec["synced"] = synced
    return save(rec, root)


def pending_retro(root=None):
    return [r for r in records(root) if r.get("end") and r.get("retro_pending")]


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="psai ledger", description="The local session ledger.")
    ap.add_argument("cmd", choices=["start", "end", "workflow", "escalation", "list", "show"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--tool", default="unknown")
    ap.add_argument("--id", default=None)
    ap.add_argument("--project", default=None)
    ap.add_argument("--transcript", default=None)
    ap.add_argument("--root", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--pending", action="store_true", help="list: ended sessions still waiting for a retro")
    ap.add_argument("--unsynced", action="store_true", help="list: sessions with captured items not yet in a PR")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "start":
            sid = a.id or f"{a.tool}-{os.getppid()}-{datetime.datetime.now():%Y%m%d%H%M%S}"
            start(a.tool, sid, a.project, a.transcript, a.root)
        elif a.cmd == "end":
            end(a.id, a.root)
        elif a.cmd == "workflow":
            update(a.id, a.root, workflow=a.name)
        elif a.cmd == "escalation":
            update(a.id, a.root, escalation=True)
        elif a.cmd == "show":
            print(json.dumps(current(a.root, a.id), indent=1))
        else:
            recs = records(a.root)
            if a.pending:
                recs = [r for r in recs if r.get("end") and r.get("retro_pending")]
            if a.unsynced:
                recs = [r for r in recs if unsynced(r)]
            if a.json:
                print(json.dumps(recs, indent=1))
            for r in [] if a.json else recs:
                c = r.get("captured") or {}
                print(f"{r['id']}  {r.get('tool')}  {r.get('start')} -> {r.get('end') or 'open'}  "
                      f"workflows={','.join(r.get('workflows') or []) or '-'}  inbox+{c.get('inbox', 0)} "
                      f"staged={c.get('staged', 0)}  retro={'done' if r.get('retro') else ('pending' if r.get('retro_pending') else 'no')}  "
                      f"synced={r.get('synced') or 'no'}")
    except Exception as e:  # noqa: BLE001 - never break a session over the ledger
        print(f"psai ledger: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
    sys.exit(main(sys.argv[1:]))
