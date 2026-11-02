# Project plan

Updated: 2026-11-02. Current focus: daily use on the laptop — performance and the remaining
hardware; QEMU is the regression check.

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

- The laptop boots from the USB, completed setup over Wi-Fi, and has keyboard, touchpad and
  sound. The owner finds apps and graphics faster than in Churro and gbos-x86 (an impression,
  not a benchmark); Chrome's logs show ANGLE on RADV, the AMD GPU. Brightness, HDMI frame rate,
  Bluetooth, microphones and suspend are open: see [laptop hardware](specs/laptop-hardware.md).
- Built since the owner's last boot, verified in QEMU only: fast page flips with HDMI connected,
  the emulator's generic bionic/libz (Google's builds caused about 74% of the laptop's sampled
  instruction traps), no 10 s TPM wait (`boot_completed` 59.7 s → 49.9 s in QEMU), no
  per-frame/per-second log and polling noise, and the power HAL no longer confining apps to 8 of
  the 12 CPUs.
- Image changes are readable lists and patches; updates preserve Android data. We build the
  kernel, Mesa/minigbm and the missing AMD/MediaTek modules; everything else is Google's or the
  emulator's unchanged prebuilts.
- An unchanged `make android-image` takes about 16 s and writes nothing. A changed partition is
  rebuilt in under a minute; a kernel config edit relinks in about 75 s; a new kernel source tree
  takes about an hour.
- QEMU reaches the setup screen with software rendering; setup there is not finished (parked).

Detailed status, evidence and handoffs live in the [component specs](specs/README.md).
This plan orders the work; it does not replace those records.

## Compared with the references

Both reference ports boot this laptop. This project follows Churro's working baseline, with:

- **Better here:** Google's image changes only through `remove.list`, `install.list` and `diff -u`
  patches with a reason each — no binary edits; emulator replacements are checked as drop-ins;
  incremental, data-preserving updates and no-op builds; one spec per component. Fixes neither
  reference has: the 10 s TPM wait at boot (Churro blacklists the TPM but keeps the waiting
  service), the power HAL's 8-CPU masks, system_server polling the removed face HAL, composer
  gamma log spam (Churro sets a property name the composer does not read) and HDMI page flips.
  gbos-x86 also removes `udsattestation`.
- **Behind:** Bluetooth (gbos-x86 builds btusb/btmtk for the MT7922), internal microphone and
  HDMI audio, suspend, Vulkan HWUI. Several fixes still lack a laptop test. Remaining traps are in
  signed ART and Rust code that cannot be swapped. The snapshot lacks DRM connector and cpufreq details.

## Proposed order

This is a flexible order, not a commitment to do every item.

1. **Laptop retest of the latest build — next.**
   The owner updates both the boot files (`make deploy-android`) and the OS partitions
   (`update-os.sh`), then checks HDMI frame rate, the brightness slider and boot/app speed.
   The boot snapshot and logs are retrieved either way. See [laptop hardware](specs/laptop-hardware.md).

2. **Remaining laptop hardware — one device at a time.**
   Done: AMD display, keyboard/touchpad, Wi-Fi, ALC256 speakers. Next candidates: brightness
   (if the retest fails), Bluetooth, internal microphone, HDMI audio, suspend.

3. **Improve performance — current.**
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
