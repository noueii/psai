# extensions/

The pi and omp extension, named in package.json's `"pi"` field (omp reads the same field). [psai.ts](psai.ts) appends the routing nudge, `skills/request-router/nudge.md`, to the system prompt before every agent run, except in a role agent. Keep it tiny: the nudge text lives in the skill, not here.
