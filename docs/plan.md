# Project plan

Updated: 2026-10-31. Current focus: the first Android boot on the laptop; QEMU polish is parked.

## Priorities

This is a personal Googlebook OS project for the MSI Modern 15 B7M, developed in QEMU first.
In order of importance:

1. Code and build steps that are easy to read and understand.
2. Little maintenance: use upstream code unchanged; patch only when nothing else works.
3. Fast repeat builds: the first build may take hours; after that, rebuild only what changed,
   in seconds where possible, and preserve Android data.
4. Good runtime performance on this machine.

This is a personal project, not a public distribution. Prefer a simple solution for this setup over
general-purpose infrastructure. Keep checks that protect data or catch likely regressions; match
validation effort to the change. Use official prebuilts unchanged where they fit, build from
source what we change, never edit binaries, and keep every carried patch small, explained and
removable once upstream covers it.

## Where we are

- The source-built kernel, Mesa softpipe and software security services reach the QEMU setup
  screen with working input. Softpipe is a slow correctness baseline, not the performance goal.
- Image changes are readable lists and patches. Incremental updates preserve Android data.
  QEMU kernel drivers are Google's prebuilt modules; we compile only the kernel image.
- Repeat builds of `make android-image`: about 10 s when nothing changed (Kbuild's own check 5 s,
  Mesa 1.5 s, disk check 3 s); about 17 s to rebuild `system` and 8 s for `vendor`. A kernel
  config or `gki-kernel.sh` edit relinks in about 75 s; a new kernel or Mesa source tree rebuilds
  it fully (kernel about an hour, Mesa about a minute).
- Setup completion, usable Internet access and Android on the physical laptop remain unverified.
- The owner confirmed the diagnostic USB (`make usb`) booted and shut down on the laptop.
  Its saved logs show passing instruction tests and ELAN touchpad registration; pointer
  motion/gestures remain untested. See [USB diagnostics](specs/usb-diagnostic.md).
- The owner agreed the first laptop boot plan (M1, below). QEMU already boots to the setup screen,
  which is enough for now. The BUP Slim USB linked at USB 2.0 (about 39 MB/s); it needs a
  USB 3 port before Android's speed means anything.
- Agent guidance now favors readable changes, quick iteration and focused verification.

Detailed status, evidence and handoffs live in the [component specs](specs/README.md).
This plan orders the work; it does not replace those records.

## Proposed order

This is a flexible order, not a commitment to do every item.

1. **First Android boot on the laptop — current.**
   Milestone M1 (agreed): the QEMU disk's partition layout on the USB, our GKI kernel and Android
   initrd loaded by GRUB, and the keyboard, touchpad and kernel log on the laptop's screen. The
   Android UI is not expected yet. Kernel and initrd updates reach the USB through its mounted
   boot partition, without sudo; OS partitions are rewritten with sudo and the owner's approval.
   The same USB image is booted in QEMU through UEFI first. See
   [laptop hardware](specs/laptop-hardware.md). The existing diagnostic USB is a separate system:
   see [USB diagnostics](specs/usb-diagnostic.md).

2. **Laptop graphics and drivers — next.**
   The `amdgpu` module and firmware (M2), then Android's UI on the AMD GPU (M3), then Wi-Fi,
   Bluetooth, audio and power (M4), one device at a time. Each step is planned with the owner first.

3. **Improve performance — once the desktop runs on the laptop.**
   Measure build time, startup time and UI responsiveness separately. Identify the main bottleneck
   and compare simple options before changing the graphics path. See [graphics](specs/graphics.md).

4. **Understand and simplify the build — alongside the laptop work.**
   Follow one build path at a time, starting with image changes and partition rebuilding. Prefer
   explaining and simplifying existing code over adding features. Keep incremental builds fast and
   verify that Android data is preserved. See [OS image](specs/os-image.md) and [boot](specs/boot.md).
   Review each carried change (the `*.patch` files under [android/](../android/), the Churro kernel
   patch and [crossystem-qemu.c](../android/crossystem-qemu.c)). Keep it only if upstream code
   or settings cannot do the job, and record why.
   Caching idea (not approved): keep one source tree per component and update it in place, so a
   new tag or patch recompiles only the files that changed; optionally add ccache. Checking it
   needs one full kernel rebuild.

5. **Make QEMU useful for development — parked.**
   Finish setup, reach the desktop and verify network access. Check that the VM can restart
   without losing Android data. See [QEMU](specs/qemu.md) and [security](specs/security.md).

## How we track progress

- Work through one review step at a time so the build stays understandable.
- Use the component specs for detailed status; update this plan only when priorities or phases change.
- Choose tests and builds that fit the change. Do not rerun a full QEMU boot for documentation edits.

## Not a current goal

KernelSU/root, dual boot, installers, broad hardware support and public release infrastructure.
Upstream contributions may come later; for now, focus on clear, useful findings and patches.
