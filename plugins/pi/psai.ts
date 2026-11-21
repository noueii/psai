// pi extension: append the live psai context to the system prompt before every agent run.
// It also opens and closes the session's ledger record (session_start, session_shutdown).
// Installed as ~/.pi/agent/extensions/psai.ts (a link). Reads $PSAI_HOME or ~/.psai each time.
// pi has no subagents: work spawns a role as `PSAI_ROLE=<role> pi -p ...`, and harness.py then prints the role-mode text.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function context(): string {
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

function ledger(args: string[]): void {
  // the local session ledger (scripts/ledger.py); best-effort, never breaks a session
  const h = process.env.PSAI_HOME || join(homedir(), ".psai");
  const script = join(h, "scripts", "ledger.py");
  if (!existsSync(script) || process.env.PSAI_ROLE) return;
  try {
    execFileSync("python3", [script, ...args], { stdio: "ignore" });
  } catch {}
}

function sid(ctx: any): string {
  try {
    return String(ctx?.sessionManager?.getSessionId?.() || "");
  } catch {
    return "";
  }
}

export default function (pi: any) {
  pi.on("session_start", async (_e: any, ctx: any) => {
    if (!sid(ctx)) return;
    ledger(["start", "--tool", "pi", "--id", sid(ctx), "--project", ctx?.cwd || process.cwd()]);
  });
  pi.on("session_shutdown", async (_e: any, ctx: any) => {
    if (!sid(ctx)) return;
    ledger(["end", "--id", sid(ctx)]);
  });
  pi.on("before_agent_start", async (event: any) => {
    const ctx = context();
    if (!ctx) return;
    return { systemPrompt: `${event.systemPrompt}\n\n${ctx}` };
  });
}
