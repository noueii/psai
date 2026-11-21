# template/

What `psai new-stack <name>` copies to start a stack (ADR 0011, section 1.2). Upstream-owned: a new stack is made from it, never edited here. [stack/](stack/stack.yaml) holds `stack.yaml` with placeholders (`__NAME__`, `__DESCRIPTION__`, `__AUTHOR__`, `__PSAI__`), a README per content folder saying what belongs there, and a CI workflow that runs `psai check .`.
