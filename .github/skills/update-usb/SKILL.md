---
name: update-usb
description: "Use when preparing a gbos-dali Android USB OS update: build approved changes, guide the owner through USB selection and confirmation, preserve userdata and metadata, and verify updater results without agent physical-disk writes."
---

# Update the existing Android USB

## Ownership and safety

This skill guides the owner; it does not authorize the agent to write block devices.
Read [project rules](../../../AGENTS.md), the
[update instructions](../../../README.md#updating-the-existing-android-usb) and the
[image spec](../../../docs/specs/os-image.md).
Never run physical-write commands, supply confirmation automatically, collect passwords,
format a disk, resize partitions, reset Android data or weaken updater safeguards.
Do not treat a request to prepare an update as approval for unrelated code changes.

## Procedure

1. Check the worktree and establish the intended changes. Confirm final implementation and
   validation approval before tests/builds. Stop only a task-owned VM before image rebuilding;
   ask the owner to stop any other VM. Do not recreate `out/android/disk.img`.
2. Use the [image validation workflow](../validate-image/SKILL.md) for the approved change.
   Verify the kernel and signed modules belong to the same build. Include both OS and boot
   files; copying a new kernel alone can leave incompatible modules.
3. Give the owner this host command:
   ```sh
   make update-usb JOBS=12
   ```
   It builds the regular Android image and starts the existing
   [interactive updater](../../../tools/update_usb.py). Do not invoke it on the owner's behalf.
4. Explain the owner's checks: select the intended USB by model/serial/capacity, ensure its
   partitions are unused, inspect the proposed OS/boot updates and the final device identity,
   then answer `y` or `yes` at `[y/N]` only if correct. Enter cancels. Never guess `/dev/sdX`,
   auto-unmount user filesystems, or offer raw copying as a shortcut.
5. Layout verification and partition hash comparisons can take a while, especially over USB 2.
   Do not interpret quiet comparison output as a hang or interrupt a write casually.
   The updater checks layout/identity, plans changes, preserves userdata/metadata/partition
   tables, revalidates before writing and verifies read-back.
6. Interpret results accurately:
   - `USB is already up to date; nothing written.` is a valid no-op, not a failed update.
   - Require the updater's verified-success output before claiming deployment succeeded.
   - On refusal/error, keep the exact message and diagnose it; never bypass identity, mount,
     layout or hash checks. For an interrupted update, follow the tool's rerun guidance on the
     same verified USB; do not reflash or recreate data.
7. Ask the owner to safely unplug before booting, choose the intended current boot entry,
   retest the changed behavior and retrieve relevant logs using the
   [diagnosis workflow](../diagnose-laptop/SKILL.md).

Report build validation separately from owner-reported deployment and hardware results.
Do not claim physical success from a local image build or infer it from a commit message.
