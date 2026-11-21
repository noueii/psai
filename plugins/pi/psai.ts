// pi extension: append the live psai context to the system prompt before every agent run.
// Installed as ~/.pi/agent/extensions/psai.ts (a link). Reads $HARNESS_HOME or ~/.harness each time.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function context(): string {
  const h = process.env.HARNESS_HOME || join(homedir(), ".harness");
  const shown = process.env.HARNESS_HOME ? h : "~/.harness";
  const script = join(h, "scripts", "harness.py");
  if (!existsSync(script)) return "";
  try {
    return execFileSync("python3", [script, "context", h, shown], { encoding: "utf8" });
  } catch {
    return "";
  }
}

export default function (pi: any) {
  pi.on("before_agent_start", async (event: any) => {
    const ctx = context();
    if (!ctx) return;
    return { systemPrompt: `${event.systemPrompt}\n\n${ctx}` };
  });
}
