#!/usr/bin/env python3
"""Draw workflows as Mermaid or SVG, and keep the Mermaid diagrams embedded in READMEs up to date.

Usage:
  graph.py <root> --mermaid <workflow>     print Mermaid for workflows/<workflow>.yaml
  graph.py <root> --svg <workflow>         print a static SVG
  graph.py <root> --update-readme          refresh embedded diagrams; add a block to <root>/README.md for each
                                           workflow that lacks one
  graph.py <root> --check-readme           exit 1 if any embedded diagram is missing or stale

A block is <!-- graph:<path-to-workflow.yaml>:start --> ... <!-- graph:<path>:end -->, with the path relative to the
README's folder, or the short form graph:<name> for <root>/workflows/<name>.yaml.
Each node shows its role (and what the role may change) and the files it reads (step and role `read:`).
Loops back are dotted, with their limit.
"""
import os
import re
import sys
from html import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402


def label(text):
    return '"' + str(text).replace('"', "'") + '"'


def reads(root, n):
    out = []
    for p in [n.get("step")] + ([f"roles/{n['role']}.md"] if n.get("role") else []):
        fp = os.path.join(root, p) if p else None
        if fp and os.path.exists(fp):
            out += [r for r in harness.frontmatter(fp).get("read", []) or [] if r not in out]
    return out


def role_line(root, n):
    if not n.get("role"):
        return ""
    fp = os.path.join(root, "roles", f"{n['role']}.md")
    may = harness.frontmatter(fp).get("may_change") if os.path.exists(fp) else None
    return n["role"] + (f" · may change: {may}" if may else "")


def short(p):
    return os.path.splitext(os.path.basename(p))[0]


def mermaid(root, wf):
    nodes, start = wf["nodes"], wf["start"]
    order = list(nodes)
    rank = {nid: i for i, nid in enumerate(order)}
    out = ["flowchart TD", f'  START(({label("task")})) --> {start}']
    for nid in order:
        n = nodes[nid] or {}
        if n.get("terminal"):
            out.append(f'  {nid}((({label(nid.upper())})))')
            continue
        if "return" in n:
            out.append(f'  {nid}{{{{{label("ESCALATE to the human")}}}}}')
            continue
        if "handoff" in n:
            out.append(f'  {nid}[/{label("handoff: " + n["handoff"])}\\]')
            continue
        text = ("human: " if n.get("human") and not nid.startswith("human") else "") + nid.replace("_", " ")
        if n.get("role"):
            text += f"<br/><i>{escape(role_line(root, n))}</i>"
        if n.get("fan_out"):
            text += "<br/>lenses: " + ", ".join(n["fan_out"])
        if n.get("skill"):
            text += f"<br/>skill: {n['skill']}"
        r = reads(root, n)
        if r:
            text += "<br/><small>reads: " + ", ".join(short(x) for x in r) + "</small>"
        shape = ("[/", "/]") if n.get("human") else ("[", "]")
        out.append(f"  {nid}{shape[0]}{label(text)}{shape[1]}")
    for nid in order:
        n = nodes[nid] or {}
        for e in n.get("next", []) or []:
            to = e["to"]
            back = to in rank and rank[to] <= rank[nid] and "return" not in (nodes.get(to) or {})
            text = e.get("when", "")
            limit = harness.edge_limit(wf, nid, e)
            if limit:
                text += f" (max {limit})"
            arrow = "-.->" if back else "-->"
            out.append(f"  {nid} {arrow}" + (f"|{label(text)}| " if text else " ") + to)
    out += [
        "  classDef human fill:#fef3c7,stroke:#b45309,color:#451a03",
        "  classDef role fill:#e0f2fe,stroke:#0369a1,color:#082f49",
        "  classDef esc fill:#fee2e2,stroke:#b91c1c,color:#450a0a",
        "  classDef done fill:#dcfce7,stroke:#15803d,color:#052e16",
    ]
    for nid in order:
        n = nodes[nid] or {}
        cls = ("done" if n.get("terminal") or "handoff" in n else "esc" if "return" in n
               else "human" if n.get("human") else "role" if n.get("role") else None)
        if cls:
            out.append(f"  class {nid} {cls}")
    return "\n".join(out)


# ---------- SVG (static, no dependencies beyond PyYAML) ----------
W, H, GAP, CX, TOP = 300, 52, 34, 420, 50
STYLE = {"role": ("#e0f2fe", "#0369a1", "#082f49"), "human": ("#fef3c7", "#b45309", "#451a03"),
         "esc": ("#fee2e2", "#b91c1c", "#450a0a"), "done": ("#dcfce7", "#15803d", "#052e16"),
         "plain": ("#f4f4f5", "#71717a", "#18181b")}


def _t(x, y, s, size=12, anchor="start", weight="normal", fill="currentColor"):
    return (f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" '
            f'fill="{fill}" paint-order="stroke" stroke="#fff" stroke-width="3">{escape(s)}</text>')


def svg(root, wf):
    nodes, start = wf["nodes"], wf["start"]
    col = [nid for nid in nodes if "return" not in (nodes[nid] or {})]
    rank = {nid: i for i, nid in enumerate(col)}
    y = {nid: TOP + 40 + i * (H + GAP) for i, nid in enumerate(col)}
    left, right = CX - W / 2, CX + W / 2
    esc_y, esc_x = (TOP + 40 + (len(col) - 1) * (H + GAP)) / 2, 30
    parts, lane_r, lane_l = [], 0, 0
    for nid in col:
        for e in (nodes[nid] or {}).get("next", []) or []:
            to, lab = e["to"], e.get("when", "")
            limit = harness.edge_limit(wf, nid, e)
            lab += f" (max {limit})" if limit else ""
            sy = y[nid] + H / 2
            if to not in rank:  # escalate
                parts.append(f'<path d="M{left},{sy} L{esc_x + 160},{esc_y + 30}" fill="none" stroke="#b91c1c" '
                             f'stroke-width="1.3" marker-end="url(#a)"/>')
                parts.append(_t(left - 6, sy - 5, lab, 11, "end"))
            elif rank[to] <= rank[nid]:
                lx = right + 30 + lane_r * 24
                lane_r += 1
                parts.append(f'<path d="M{right},{sy} H{lx} V{y[to] + H / 2} H{right + 2}" fill="none" '
                             f'stroke="currentColor" stroke-width="1.3" stroke-dasharray="5 4" marker-end="url(#a)"/>')
                parts.append(_t(right + 6, sy - 4, lab, 11))
            elif rank[to] - rank[nid] == 1:
                parts.append(f'<path d="M{CX},{y[nid] + H} V{y[to] - 2}" stroke="currentColor" stroke-width="1.3" '
                             f'marker-end="url(#a)"/>')
                if lab:
                    parts.append(_t(CX + 8, (y[nid] + H + y[to]) / 2 + 4, lab, 11))
            else:
                lx = left - 24 - lane_l * 20
                lane_l += 1
                parts.append(f'<path d="M{left},{sy} H{lx} V{y[to] + H / 2} H{left - 2}" fill="none" '
                             f'stroke="currentColor" stroke-width="1.3" marker-end="url(#a)"/>')
                parts.append(_t(left - 6, sy - 5, lab, 11, "end"))
    parts.append(f'<path d="M{CX},{TOP} V{y[start] - 2}" stroke="currentColor" stroke-width="1.3" marker-end="url(#a)"/>')
    parts.append(_t(CX, TOP - 8, "task", 12, "middle", "600"))
    for nid in col:
        n = nodes[nid] or {}
        k = "done" if n.get("terminal") or "handoff" in n else "human" if n.get("human") else "role" if n.get("role") else "plain"
        f, st, tc = STYLE[k]
        dash = ' stroke-dasharray="4 3"' if n.get("human") else ""
        parts.append(f'<rect x="{left}" y="{y[nid]}" width="{W}" height="{H}" rx="7" fill="{f}" stroke="{st}" stroke-width="1.5"{dash}/>')
        title = ("human: " if n.get("human") and not nid.startswith("human") else "") + (nid.upper() if n.get("terminal") else nid.replace("_", " "))
        sub = role_line(root, n)
        rd = ", ".join(short(x) for x in reads(root, n))
        parts.append(_t(CX, y[nid] + 18, title, 13, "middle", "600", tc))
        if sub:
            parts.append(_t(CX, y[nid] + 32, sub, 10.5, "middle", "normal", tc))
        if rd:
            parts.append(_t(CX, y[nid] + 45, "reads: " + rd, 10, "middle", "normal", tc))
    if any("return" in (n or {}) for n in nodes.values()):
        f, st, tc = STYLE["esc"]
        parts.append(f'<rect x="{esc_x}" y="{esc_y}" width="160" height="60" rx="8" fill="{f}" stroke="{st}" stroke-width="1.5"/>')
        parts.append(_t(esc_x + 80, esc_y + 26, "ESCALATE", 13, "middle", "600", tc))
        parts.append(_t(esc_x + 80, esc_y + 44, "answer resumes the asker", 10.5, "middle", "normal", tc))
    width, height = right + 40 + lane_r * 24 + 150, TOP + 40 + len(col) * (H + GAP)
    defs = ('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" '
            f'font-family="system-ui,sans-serif" style="color:#171717">{defs}{"".join(parts)}</svg>')


# ---------- README blocks ----------
BLOCK = re.compile(r"<!-- graph:(?P<ref>[^ ]+?):start -->\n.*?<!-- graph:(?P=ref):end -->", re.S)


def render_block(ref, readme_dir, root):
    path = os.path.join(readme_dir, "workflows", f"{ref}.yaml") if "/" not in ref else os.path.join(readme_dir, ref)
    if not os.path.exists(path):  # e.g. an eval copy without the test fixture: leave the block alone
        return None
    wroot = os.path.dirname(os.path.dirname(os.path.abspath(path)))
    body = mermaid(wroot, harness.load(path))
    return f"<!-- graph:{ref}:start -->\n```mermaid\n{body}\n```\n<!-- graph:{ref}:end -->"


def readmes(root):
    for dp, dirs, fs in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "results", "__pycache__")]
        if "README.md" in fs:
            yield os.path.join(dp, "README.md")


def refresh(root, write):
    stale = []
    for rp in readmes(root):
        text = open(rp).read()
        new = BLOCK.sub(lambda m: render_block(m.group("ref"), os.path.dirname(rp), root) or m.group(0), text)
        if os.path.abspath(rp) == os.path.abspath(os.path.join(root, "README.md")):
            for path in harness.workflow_files(root):
                name = os.path.basename(path)[:-5]
                if f"<!-- graph:{name}:start -->" not in new:
                    if "## Workflows" not in new:
                        new = new.rstrip("\n") + "\n\n## Workflows\n"
                    i = new.index("## Workflows") + len("## Workflows\n")
                    add = f"\n### {name}\n{render_block(name, root, root)}\n"
                    new = new[:i] + add + new[i:]
        if new != text:
            stale.append(os.path.relpath(rp, root))
            if write:
                open(rp, "w").write(new)
    return stale


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    root, cmd = argv[0], argv[1]
    if cmd in ("--mermaid", "--svg"):
        wf = harness.load(os.path.join(root, "workflows", f"{argv[2]}.yaml"))
        print(mermaid(root, wf) if cmd == "--mermaid" else svg(root, wf))
    elif cmd == "--update-readme":
        for s in refresh(root, True):
            print(f"updated {s}")
    elif cmd == "--check-readme":
        stale = refresh(root, False)
        for s in stale:
            print(f"  FAIL {s}: workflow diagram missing or stale (run scripts/graph.py <root> --update-readme)")
        return 1 if stale else 0
    else:
        sys.exit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
