// opencode plugin: add the live psai context to the system prompt of every request.
// Installed as ~/.config/opencode/plugins/psai.js (a link). Reads $PSAI_HOME or ~/.psai each time.
// A child session (the task tool: it has a parentID) or a session with $PSAI_ROLE gets the role-mode text: no routing.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function context(sub = false) {
  const h = process.env.PSAI_HOME || join(homedir(), ".psai");
  const shown = process.env.PSAI_HOME ? h : "~/.psai";
  const script = join(h, "scripts", "harness.py");
  if (!existsSync(script)) return "";
  try {
    return execFileSync("python3", [script, sub ? "role-context" : "context", h, shown], { encoding: "utf8" });
  } catch {
    return "";
  }
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
  return {
    "experimental.chat.system.transform": async (input, output) => {
      const ctx = context(await child(input?.sessionID));
      if (ctx) output.system.push(ctx);
    },
  };
};
