# Component specs

One short document per component: what it must do, what works today, the decisions behind it,
and the next actions. These are the project's handoff notes: whoever picks up a component —
a person or an AI agent — starts from its spec and leaves it updated.

Read the [project plan](../plan.md) for overall priorities and the proposed order of work.
The component specs track the details; the plan keeps the overall direction in one place.

| Spec | Status | Next action |
|---|---|---|
| [Kernel (GKI)](kernel.md) | working | Validate signed AMD modules on hardware |
| [Boot chain](boot.md) | working | Physical UEFI boot (tracked in Laptop hardware) |
| [OS image and disk](os-image.md) | working | — (stable; the USB layout is tracked in Laptop hardware) |
| [Security services](security.md) | working (software keys) | Confirm setup/account flows accept software keys |
| [Graphics](graphics.md) | partial | Validate the built AMD stack; QEMU softpipe still works |
| [QEMU VM](qemu.md) | parked | — (SetupWizard and networking can wait) |
| [Laptop hardware](laptop-hardware.md) | partial | USB written and verified; owner to boot the AMD candidate; physical graphics/input unverified |
| [USB diagnostics](usb-diagnostic.md) | parked | — (first laptop boot/shutdown confirmed; logs reviewed) |

**Status words:** `working` = verified as described in the spec · `partial` = some parts verified ·
`planned` = agreed, not started · `parked` = works, not being developed now.

## Rules

- Only write what was verified as working, and say how it was verified. Untested is not working.
- **Decisions** are settled. Reopening one needs the user's agreement; record the new decision and why.
- **Actions** are agreed next steps with a "done when". Unapproved ideas go under *Ideas (not approved)*.
- Keep each spec readable in a few minutes. Link to code and the [README](../../README.md); don't copy them.
- At the end of a work session, update every spec you touched and add a handoff-log entry
  (the `/handoff` prompt does this). Update the table above when a status or next action changes.

## Template

```markdown
# <Component>

**Status:** working | partial | planned | parked — one-line reason
**Last verified:** YYYY-MM-DD — how (command, evidence file)

## Goal
What this component must achieve, in one or two sentences.

## Current state
Verified: … Not verified / not working: …

## Decisions
- Choice — why.

## Files
- [path](../../path) — responsibility.

## Verify
Commands that prove it works, and what to look at.

## Pitfalls
- Specific things that cost time before, and the fix.

## Actions
- [ ] Next step — done when …

### Ideas (not approved)
- …

## Handoff log
- YYYY-MM-DD `commit` — what changed; what's left. (Newest first, at most three lines each.)
```
