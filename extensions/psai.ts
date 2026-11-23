// pi and omp extension (package.json "pi"; omp reads the same field): append psai's routing nudge to the system
// prompt before every agent run. The nudge is skills/request-router/nudge.md, read live from this package.
// A role agent (pi: started with PSAI_ROLE set; omp: a subagent) gets no nudge.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

function nudge(): string {
  try {
    return readFileSync(fileURLToPath(new URL("../skills/request-router/nudge.md", import.meta.url)), "utf8");
  } catch {
    return "";
  }
}

export default function (pi: any) {
  pi.on("before_agent_start", async (event: any, ctx: any) => {
    if (process.env.PSAI_ROLE || ctx?.agent?.kind === "sub") return;
    const text = nudge();
    if (!text) return;
    const sp = event.systemPrompt;
    return { systemPrompt: Array.isArray(sp) ? [...sp, text] : `${sp ?? ""}\n\n${text}` };
  });
}
