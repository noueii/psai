# evals/fixtures/

Inputs for tests, never installed for real.
- [textkit/](textkit/README.md): a tiny Python repo with its own tests. Each eval run works on a throwaway copy.
- [stacks/](stacks/README.md): neutral test stacks in psai 4's layout: `example` and `other`.
- [variants/](variants/README.md): folders copied over a test stack for one scenario.

A new test stack has the manifests (`.claude-plugin/`, `plugin.json`, `package.json`) and follows customize-harness's LAYOUT.md; `scripts/check.sh` checks it.
