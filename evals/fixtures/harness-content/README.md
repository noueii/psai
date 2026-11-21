# evals/fixtures/harness-content/

TEST content for the harness: the owner's coding setup (workflow, routing, steps, roles, guides, templates, role knowledge, and a global.md with owner rules). It is never installed. Tests overlay it on a throwaway copy of the vanilla harness:
- `scripts/check.sh` and `scripts/simulate.py` validate it (L0, L2);
- the L3 eval scenarios run on it.

The tree mirrors the harness root, so every file follows `LAYOUT.md`.

## coding
<!-- graph:coding:start -->
```mermaid
flowchart TD
  START(("task")) --> clarify
  clarify["clarify<br/><small>reads: spec</small>"]
  plan["plan<br/><small>reads: plan</small>"]
  plan_review[/"human: plan review<br/><small>reads: plan</small>"/]
  implement["implement<br/><i>engineer · may change: anything</i><br/><small>reads: coding-rules</small>"]
  verify_prep["verify prep<br/><i>qa · may change: tests</i><br/><small>reads: testing-rules, spec</small>"]
  verify["verify"]
  ai_review["ai review<br/><i>reviewer · may change: nothing</i><br/>lenses: correctness, spec fit, simplicity<br/><small>reads: coding-rules, testing-rules</small>"]
  human_review[/"human review<br/><small>reads: coding-rules, testing-rules</small>"/]
  sanitize["sanitize<br/><small>reads: pr-description</small>"]
  handover["handover<br/><small>reads: handover</small>"]
  escalate{{"ESCALATE to the human"}}
  ready((("READY")))
  clarify -->|"blocking question"| escalate
  clarify -->|"big"| plan
  clarify -->|"small"| implement
  plan --> plan_review
  plan_review -.->|"changes requested"| plan
  plan_review -->|"accepted"| implement
  implement -->|"checks exist and the spec is unchanged"| verify
  implement -->|"no checks yet or the spec changed"| verify_prep
  verify_prep --> verify
  verify -.->|"fail (max 2)"| implement
  verify -->|"pass"| ai_review
  ai_review -.->|"small fix (max 2)"| verify
  ai_review -.->|"rework (max 2)"| implement
  ai_review -->|"spec gap"| escalate
  ai_review -->|"clean"| human_review
  human_review -.->|"small fix"| verify
  human_review -.->|"rework"| implement
  human_review -->|"approved"| sanitize
  sanitize -.->|"a check broke (max 2)"| verify
  sanitize -->|"clean"| handover
  handover --> ready
  classDef human fill:#fef3c7,stroke:#b45309,color:#451a03
  classDef role fill:#e0f2fe,stroke:#0369a1,color:#082f49
  classDef esc fill:#fee2e2,stroke:#b91c1c,color:#450a0a
  classDef done fill:#dcfce7,stroke:#15803d,color:#052e16
  class plan_review human
  class implement role
  class verify_prep role
  class ai_review role
  class human_review human
  class escalate esc
  class ready done
```
<!-- graph:coding:end -->
