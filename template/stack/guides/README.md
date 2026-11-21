# guides/

How one kind of work must be done (prescriptive). A step or role loads a guide by listing it in `read:`. Name: `<topic>-rules.md` or `<topic>.md`. Example: psai's test stack, `evals/fixtures/stacks/example/guides/example-rules.md`.

Format: a title, then short rules as bullets. Each rule comes from the stack's author, never invented. A user who wants a different rule overrides this file in their overlay (`psai stack override`).
