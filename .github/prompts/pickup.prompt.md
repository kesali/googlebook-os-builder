---
description: "Resume one component from its spec and repository state; summarize progress and suggest a focused next step."
argument-hint: "Component: kernel, boot, os-image, security, graphics, qemu, laptop-hardware"
agent: "agent"
---
Resume the component named in the argument. If none was given, use the current phase in
[docs/plan.md](../../docs/plan.md). If this is a step-by-step review, continue from the last
agreed step rather than starting a broad audit.

1. Read [AGENTS.md](../../AGENTS.md) and the component spec. Check `git status --short` and the
   latest relevant commits; check VM/disk state only if the task could affect them.
2. Briefly summarize verified progress, anything stale or uncertain, and one useful next step.
   Say why it helps and how you would verify it.
3. If the user is reviewing step by step, explain that step and pause for feedback before continuing.
