---
description: "Use when updating component specs, handoff notes, status or next actions in docs/specs/."
applyTo: "docs/specs/**"
---
# Component specs

- Follow the template and rules in [docs/specs/README.md](../../docs/specs/README.md).
- Status, "Last verified" and "Current state" contain only what was actually verified, with the
  command or evidence file. Put untested items under "Not verified".
- Actions are checkboxes with a "done when". When one is done, remove it and record it in the
  handoff log. Ideas without the user's agreement go under "Ideas (not approved)".
- Handoff log: newest first, date + commit (or `uncommitted`), at most three lines.
- Keep specs short and human-readable; link code instead of copying it.
- Update the index table in `docs/specs/README.md` when a status or next action changes.
