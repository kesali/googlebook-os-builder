# Project plan

Updated: 2026-10-31. Current focus: understand and simplify the existing build.

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
- Image changes are readable lists and patches. Incremental updates preserve Android data; the
  current image and module ramdisk match the previous build byte-for-byte.
- Repeat builds of `make android-image`: about 10 s when nothing changed (Kbuild's own check 5 s,
  Mesa 1.5 s, disk check 3 s); about 17 s to rebuild `system` and 8 s for `vendor`. A kernel
  config or `gki-kernel.sh` edit relinks in about 50 s; a new kernel or Mesa source tree rebuilds
  it fully (kernel about an hour, Mesa about a minute).
- Setup completion, usable Internet access and Android on the physical laptop remain unverified.
- Agent guidance now favors readable changes, quick iteration and focused verification.

Detailed status, evidence and handoffs live in the [component specs](specs/README.md).
This plan orders the work; it does not replace those records.

## Proposed order

This is a flexible order, not a commitment to do every item.

1. **Understand and simplify the build — current.**
   Follow one build path at a time, starting with image changes and partition rebuilding. Prefer
   explaining and simplifying existing code over adding features. Keep incremental builds fast and
   verify that Android data is preserved. See [OS image](specs/os-image.md) and [boot](specs/boot.md).
   Review each carried change (the `*.patch` files under [android/](../android/), the Churro kernel
   patch and [crossystem-qemu.c](../android/crossystem-qemu.c)). Keep it only if upstream code
   or settings cannot do the job, and record why.
   Caching idea (not approved): keep one source tree per component and update it in place, so a
   new tag or patch recompiles only the files that changed; optionally add ccache. Checking it
   needs one full kernel rebuild.

2. **Make QEMU useful for development — next.**
   Finish setup, reach the desktop and verify network access. Check that the VM can restart
   without losing Android data. See [QEMU](specs/qemu.md) and [security](specs/security.md).

3. **Improve performance — after the desktop works.**
   Measure build time, startup time and UI responsiveness separately. Identify the main bottleneck
   and compare simple options before changing the graphics path. See [graphics](specs/graphics.md).

4. **Try the OS on the laptop — later.**
   First decide the smallest useful driver set and a safe boot/update method. Add hardware support
   one device at a time. The existing USB target is only a separate diagnostic system. See
   [laptop hardware](specs/laptop-hardware.md) and [USB diagnostics](specs/usb-diagnostic.md).

## How we track progress

- Work through one review step at a time so the build stays understandable.
- Use the component specs for detailed status; update this plan only when priorities or phases change.
- Choose tests and builds that fit the change. Do not rerun a full QEMU boot for documentation edits.

## Not a current goal

KernelSU/root, dual boot, installers, broad hardware support and public release infrastructure.
Upstream contributions may come later; for now, focus on clear, useful findings and patches.
