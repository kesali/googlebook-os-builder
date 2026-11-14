# Component specs

These are current-state notes for the components in [the project plan](../plan.md).
Use Git history for past implementation and validation details; keep these files focused
on what works now, constraints that still apply, and the next agreed action.

| Spec | Current status | Next action |
|---|---|---|
| [Kernel (GKI)](kernel.md) | partial; ABI-preserving kernel and selected modules build | Owner checks remaining physical drivers and brightness |
| [Boot chain](boot.md) | partial; enforcing QEMU and firmware-free laptop boot verified | Owner captures logs from a current laptop boot |
| [OS image and disk](os-image.md) | partial; image build and direct QEMU pass | Owner tests fresh installation and USB update |
| [Security services](security.md) | working with software keys; hardware-backed keys unavailable | Owner verifies PIN setup and persistence |
| [Graphics](graphics.md) | partial; QEMU selector sets softpipe under enforcing SELinux; physical GPU behavior unverified | Owner verifies Intel HAL loading and native display |
| [QEMU VM](qemu.md) | parked; bounded boot reaches Android welcome screen with softpipe | Finish setup/network checks if QEMU work resumes |
| [Laptop hardware](laptop-hardware.md) | partial; graphics work, camera does not on Mesa 26.3.0 | Retrieve current diagnostic logs and investigate camera |

**Status words:** `working` means verified as described; `partial` means some
requirements remain unverified; `planned` means agreed but not started; `parked`
means working enough to pause development.

## Updating a spec

- Keep status, verification date, and current state factual. Put unknowns under
  **Not verified**; don't treat older results as current.
- Keep decisions that still constrain implementation, useful file links, focused
  verification commands, real pitfalls, and agreed next actions.
- Do not add a change log or dated history. Git history records past changes; ignored
  `out/` files may hold detailed evidence.
- Keep the spec short and update the index when status or next action changes.

## Template

```markdown
# <Component>

**Status:** working | partial | planned | parked — current summary
**Last verified:** YYYY-MM-DD — command or owner-reported result

## Goal
What this component must do.

## Current state
What works, what does not, and what remains unverified.

## Decisions
- Settled constraints that future changes must preserve.

## Files
Link directly to implementation using paths relative to this spec.

## Verify
Focused commands and the evidence to inspect.

## Pitfalls
- Current, actionable failure modes only.

## Actions
- [ ] Next agreed step — done when …
```
