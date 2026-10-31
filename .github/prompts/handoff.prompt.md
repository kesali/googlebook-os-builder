---
description: "Write a handoff: update the affected component specs (status, verified state, actions, log) from this session's work."
agent: "agent"
---
Record a handoff for the work done in this session, following
[docs/specs/README.md](../../docs/specs/README.md).

1. Find what changed: `git status --short`, `git --no-pager diff --stat`, and commits since the newest
   handoff-log entry of each affected spec. Map changed files to specs using each spec's **Files** list.
2. For each affected spec:
   - change **Status**, **Last verified** and **Current state** only with evidence from this
     session (command and result, or evidence file); otherwise list it under "Not verified";
   - add new **Pitfalls** that cost time, and new or changed **Decisions** the user agreed to;
   - remove finished **Actions** and add agreed next steps with a "done when";
   - add one handoff-log entry at the top: date, commit or `uncommitted`, what changed, what is left.
3. Update the index table in `docs/specs/README.md` if a status or next action changed.
4. Show the spec changes (`git --no-pager diff docs/specs`). Do not commit unless the user asks.
