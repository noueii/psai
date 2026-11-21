// pi extension: append the live psai context to the system prompt before every agent run.
// It also opens and closes the session's ledger record (session_start, session_shutdown).
// Installed as ~/.pi/agent/extensions/psai.ts (a link). Runs `psai context` live each time.
// pi has no subagents: work spawns a role as `PSAI_ROLE=<role> pi -p ...`, and harness.py then prints the role-mode text.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

// The one bootstrap: the home, and the psai command in it (framework/ in the stacks layout, else the clone itself,
// else psai on PATH). Everything else goes through the psai command.
function home(): string {
  return process.env.PSAI_HOME || join(homedir(), ".psai"); // psai-bootstrap
}

function psai(): string {
  for (const p of [join(home(), "framework", "scripts", "psai.py"), join(home(), "scripts", "psai.py")]) // psai-bootstrap
    if (existsSync(p)) return p;
  try {
    return execFileSync("sh", ["-c", "command -v psai"], { encoding: "utf8" }).trim();
  } catch {
    return "";
  }
}

function context(): string {
  const script = psai();
  if (!script) return "";
  const shown = process.env.PSAI_HOME ? home() : "~/.psai";
  try {
    return execFileSync("python3", [script, "context", home(), shown], { encoding: "utf8" });
  } catch {
    return "";
  }
}

function ledger(args: string[]): void {
  // the local session ledger (`psai ledger`); best-effort, never breaks a session
  const script = psai();
  if (!script || process.env.PSAI_ROLE) return;
  try {
    execFileSync("python3", [script, "ledger", ...args], { stdio: "ignore" });
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
