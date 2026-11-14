---
description: "Record a completed change in its affected component spec, with concise verified status and next action."
agent: "agent"
---
Update the current state in the affected component spec, following
[AGENTS.md](../../AGENTS.md) and [docs/specs/README.md](../../docs/specs/README.md). Keep it short.

1. Check `git status --short` and `git diff --stat`. Update only the spec for the component changed.
2. Update the current status and verified state, and keep unverified behavior clearly marked.
   Do not infer test results from a summary or commit message.
3. Update the next agreed action and spec index if either changed. Do not append a change log;
   Git history records what changed.
4. Do not start another implementation as part of the handoff.
