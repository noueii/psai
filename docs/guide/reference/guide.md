# A guide

`guides/<name>.md`: prescriptive prose for one kind of work ("how we write release notes"), attached to a step or role with `read:`. No frontmatter needed. Keep one guide per concern, and short: everything a guide says is read on every step that attaches it.

```md
# Release notes

- One line per change, under 80 characters.
- Start with the verb: Add, Fix, Remove.
```
A guide used by one workflow lives in its folder; a guide several workflows use lives in `<stack>-shared/guides/`.
