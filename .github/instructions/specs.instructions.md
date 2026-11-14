---
description: "Use when updating component specs, handoff notes, status or next actions in docs/specs/."
applyTo: "docs/specs/**"
---
# Component specs

- Follow the template and rules in [docs/specs/README.md](../../docs/specs/README.md).
- Status, "Last verified" and "Current state" contain only what was actually verified, with the
  command or evidence file. Put untested items under "Not verified".
- Actions are checkboxes with a "done when". Remove an action when complete; do not append
  a historical entry. Ideas without the user's agreement go under "Ideas (not approved)".
- Keep specs focused on current state and settled constraints. Git history records past changes;
  detailed validation logs stay in the session or ignored output directory.
- Keep specs short and human-readable; link code instead of copying it.
- Update only specs directly affected by the change. Record the current verification command and
  link useful evidence only when that evidence is available.
- Update the index table in `docs/specs/README.md` when a status or next action changes.
