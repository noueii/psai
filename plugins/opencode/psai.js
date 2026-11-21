// opencode plugin: add the live psai context to the system prompt of every request.
// Installed as ~/.config/opencode/plugins/psai.js (a link). Reads $PSAI_HOME or ~/.psai each time.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function context() {
  const h = process.env.PSAI_HOME || join(homedir(), ".psai");
  const shown = process.env.PSAI_HOME ? h : "~/.psai";
  const script = join(h, "scripts", "harness.py");
  if (!existsSync(script)) return "";
  try {
    return execFileSync("python3", [script, "context", h, shown], { encoding: "utf8" });
  } catch {
    return "";
  }
}

export const Psai = async () => ({
  "experimental.chat.system.transform": async (_input, output) => {
    const ctx = context();
    if (ctx) output.system.push(ctx);
  },
});
