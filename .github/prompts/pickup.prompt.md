---
description: "Resume work on one component: read its spec, check the repository and VM state, and propose the next action."
argument-hint: "Component: kernel, boot, os-image, security, graphics, qemu, laptop-hardware, usb-diagnostic"
agent: "agent"
---
Pick up work on the component named in the argument. If none was given, use the
"Next action" column of [docs/specs/README.md](../../docs/specs/README.md) to suggest one.

1. Read [docs/specs/README.md](../../docs/specs/README.md) and the component's spec in `docs/specs/`.
2. Check the current state without changing anything:
   - `git status --short` and `git --no-pager log --oneline -5`;
   - commits since the spec's newest handoff-log entry that touch the component's files;
   - whether a VM is running (`docker ps`) and whether `out/android/disk.img` exists.
3. Reply in at most ten lines: the status, anything that contradicts the spec, and the top open
   action with a short plan for it (files to change, how it will be verified).
4. Stop and wait for the user's agreement before editing files or starting builds.
