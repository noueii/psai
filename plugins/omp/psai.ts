// omp extension: append the live psai context to the system prompt before every agent run.
// Installed as ~/.omp/agent/extensions/psai.ts (a link). Reads $PSAI_HOME or ~/.psai each time.
// A subagent (task tool: ctx.agent.kind "sub") or a session with $PSAI_ROLE gets the role-mode text: no routing.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function context(sub = false): string {
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

export default function (pi: any) {
  pi.on("before_agent_start", async (event: any, ec: any) => {
    const ctx = context(ec?.agent?.kind === "sub");
    if (!ctx) return;
    return { systemPrompt: [...(event.systemPrompt || []), ctx] };
  });
}
