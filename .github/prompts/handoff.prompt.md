---
description: "Record a completed change in its affected component spec, with concise verified status and next action."
agent: "agent"
---
Record the completed change in its affected component spec, following
[AGENTS.md](../../AGENTS.md) and [docs/specs/README.md](../../docs/specs/README.md). Keep it short.

1. Check `git status --short` and `git diff --stat`. Update only the spec for the component changed.
2. Record what changed, what was actually verified, and the next agreed action. Keep unverified
   behavior clearly marked; do not infer test results from a summary or commit message.
3. Add a brief handoff entry. Update the spec index only if its status or next action changed.
4. Do not start another implementation as part of the handoff.
