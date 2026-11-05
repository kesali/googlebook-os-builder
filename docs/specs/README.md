# Component specs

One short document per component: what it must do, what works today, the decisions behind it,
and the next actions. These are the project's handoff notes: whoever picks up a component —
a person or an AI agent — starts from its spec and leaves it updated.

Read the [project plan](../plan.md) for overall priorities and the proposed order of work.
The component specs track the details; the plan keeps the overall direction in one place.

| Spec | Status | Next action |
|---|---|---|
| [Kernel (GKI)](kernel.md) | partial; firmware handoff removed, rebuild/kABI/QEMU pass | Owner retests rebuilt image on both laptops |
| [Boot chain](boot.md) | partial; FAT32 logging focused tests pass | Owner approves image build and enforcing mount/boot checks |
| [OS image and disk](os-image.md) | partial; 107 compact-layout/logging tests pass | Owner approves image/boot/no-write repeat checks |
| [Security services](security.md) | working (software keys); unconditional portable crypto focused tests pass | Rebuild/check simplified crypto image, then setup/account flows |
| [Graphics](graphics.md) | partial; MSI video and firmware-free laptop tests owner-confirmed | Owner retests native-only rebuilt image; camera fallback unverified |
| [QEMU VM](qemu.md) | parked | Renamed setup/input verified; finishing setup/networking can wait |
| [Laptop hardware](laptop-hardware.md) | partial; Lenovo fixes and MSI regression owner-confirmed | Remaining headphone, brightness and suspend checks |

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
