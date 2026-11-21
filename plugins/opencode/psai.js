// opencode plugin: add the live psai context to the system prompt of every request.
// It also opens a ledger record for each top-level session (session.created) and closes it (session.deleted, or
// when the server goes away).
// Installed as ~/.config/opencode/plugins/psai.js (a link). Runs `psai context` live each time.
// A child session (the task tool: it has a parentID) or a session with $PSAI_ROLE gets the role-mode text: no routing.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

// The one bootstrap: the home, and the psai command in it (framework/ in the stacks layout, else the clone itself,
// else psai on PATH). Everything else goes through the psai command.
function home() {
  return process.env.PSAI_HOME || join(homedir(), ".psai"); // psai-bootstrap
}

function psai() {
  for (const p of [join(home(), "framework", "scripts", "psai.py"), join(home(), "scripts", "psai.py")]) // psai-bootstrap
    if (existsSync(p)) return p;
  try {
    return execFileSync("sh", ["-c", "command -v psai"], { encoding: "utf8" }).trim();
  } catch {
    return "";
  }
}

function context(sub = false) {
  const script = psai();
  if (!script) return "";
  const shown = process.env.PSAI_HOME ? home() : "~/.psai";
  try {
    return execFileSync("python3", [script, sub ? "role-context" : "context", home(), shown], { encoding: "utf8" });
  } catch {
    return "";
  }
}

function ledger(args) {
  // the local session ledger (`psai ledger`); best-effort, never breaks a session
  const script = psai();
  if (!script || process.env.PSAI_ROLE) return;
  try {
    execFileSync("python3", [script, "ledger", ...args], { stdio: "ignore" });
  } catch {}
}

export const Psai = async ({ client } = {}) => {
  const isChild = new Map(); // sessionID -> has a parent session
  async function child(id) {
    if (!id || !client) return false;
    if (!isChild.has(id)) {
      try {
        const r = await client.session.get({ path: { id } });
        isChild.set(id, Boolean((r?.data ?? r)?.parentID));
      } catch {
        return false;
      }
    }
    return isChild.get(id);
  }
  const open = new Set();
  const close = (id) => {
    if (open.delete(id)) ledger(["end", "--id", id]);
  };
  process.once("exit", () => [...open].forEach(close));
  return {
    event: async ({ event } = {}) => {
      const info = event?.properties?.info;
      if (event?.type === "session.created" && info?.id && !info.parentID) {
        open.add(info.id);
        isChild.set(info.id, false);
        ledger(["start", "--tool", "opencode", "--id", info.id, "--project", info.directory || process.cwd()]);
      } else if (event?.type === "session.deleted" && info?.id) {
        close(info.id);
      } else if (event?.type === "server.instance.disposed") {
        [...open].forEach(close);
      }
    },
    "experimental.chat.system.transform": async (input, output) => {
      const ctx = context(await child(input?.sessionID));
      if (ctx) output.system.push(ctx);
    },
  };
};
