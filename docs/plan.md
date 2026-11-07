# Project plan

Updated: 2026-11-04. Current focus: polish the existing builder and make adding your own
hardware recipes understandable. Further hardware enablement and tuning are deferred unless
daily use exposes a practical problem. QEMU is the regression check.

## Priorities

This is a personal Googlebook OS builder, developed on the MSI Modern 15 B7M and Lenovo
E50-80 in QEMU first.
In order of importance:

1. Code and build steps that are easy to read and understand.
2. Little maintenance: use upstream code unchanged; patch only when nothing else works.
3. Fast repeat builds: the first build may take hours; after that, rebuild only what changed,
   in seconds where possible, and preserve Android data.
4. Good runtime performance on the tested laptops.

This is a personal project, not a public distribution. Prefer a simple solution for this setup over
general-purpose infrastructure. Keep checks that protect data or catch likely regressions; match
validation effort to the change. Use official prebuilts unchanged where they fit, build from
source what we change, never edit binaries, and keep every carried patch small, explained and
removable once upstream covers it.

## Where we are

- Both laptops boot the combined recipe image. Lenovo Bluetooth, audio, microphone, camera,
  Chrome and smaller UI at density 160 are owner-confirmed; the MSI's speaker, microphone and
  camera regression check is also confirmed. Lenovo uses Iris GLES and hasvk Vulkan.
- The MSI boots from USB, completed setup over Wi-Fi, and has working input, speakers,
  built-in microphone, camera preview and video recording. The owner finds apps and graphics
  faster than in Churro and gbos-x86 (an impression, not a benchmark); Chrome's logs show ANGLE
  on RADV. The owner reports HDMI display performance is fine, without a frame-rate measurement.
  Brightness, MSI Bluetooth pairing, HDMI audio and suspend remain open:
  [laptop hardware](specs/laptop-hardware.md).
- The laptop has received the fast page flips, generic bionic/libz, TPM-wait and logging fixes,
  and power HAL changes; their individual runtime effects have not all been measured on the laptop.
  Boot logs retain the startup, and the snapshot records displays and the CPU governor. The normal
  GRUB entry no longer draws early messages through the firmware console, which took 61 s of the
  earlier 104 s boot.
- Image changes are readable lists and patches; updates preserve Android data. We build the
  kernel, Mesa/minigbm and the missing laptop modules; everything else is Google's or the
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
- **Still open:** Bluetooth pairing (the missing MT7922 firmware is installed), HDMI audio,
  headphone output, brightness and suspend. The optional Vulkan HWUI profile showed no noticeable
  improvement in the owner's test; broader app regression testing remains. Remaining traps are in
  signed ART and Rust code that cannot be swapped.

## Proposed order

This is a flexible order, not a commitment to do every item.

1. **Reconcile TODOs and component specs — next.**
   Close only checks already established by evidence or owner confirmation. Keep genuinely
   unverified hardware checks visible but deferred, rather than treating them as current blockers.

2. **Explain adding a hardware recipe.**
   Walk through an existing laptop from hardware IDs to reused drivers, device-specific files,
   validation and physical results. Explain shared-driver versus device ownership using the
   existing [recipe format](build-guide.md#hardware-recipes), not a new configuration format.
   Use the walkthrough to identify actual usability gaps before adding tools.

3. **Polish the build and update workflow.**
   Improve readability, actionable errors and progress one focused change at a time.
   The existing USB progress TODO covers separate write/read-back progress, bytes, percentage,
   throughput and estimated remaining time; preserve device selection and verification safeguards.
   Compact installation images remain deferred.
   - [ ] Add Podman support alongside Docker — deferred; do not implement yet.
     Done when both runtimes use the same builder definition and pass fresh-build, no-write
     repeat and QEMU checks, including file ownership and `/dev/kvm` permissions.

4. **Make recipe composition inspectable and maintainable.**
   - Summarize selected recipes and their patches, modules and firmware through existing tooling.
   - Assess `make hardware-check` before adding checks for concrete gaps such as conflicting
     installs or incompatible selections; fail before expensive builds.
   - Keep concise per-device verification evidence, limitations and workarounds beside recipes.
     A successful build is not physical hardware verification.
   - Record upstream status and removal conditions beside carried fixes, without a new framework.
   Read-only hardware detection, missing-driver guidance and device-contribution guidance remain
   follow-up ideas; detection must be advisory, not automatic modification or a support promise.

5. **Understand and simplify the build — alongside polish.**
   Follow one build path at a time, starting with image changes and partition rebuilding. Prefer
   explaining and simplifying existing code over adding features. Keep incremental builds fast and
   verify that Android data is preserved. See [OS image](specs/os-image.md) and [boot](specs/boot.md).
   Review each carried change (the `*.patch` files under [android/](../android/), the Churro kernel
   patch and [crossystem-qemu.c](../android/crossystem-qemu.c)). Keep it only if upstream code
   or settings cannot do the job, and record why.
   Caching idea (not approved): keep one source tree per component and update it in place, so a
   new tag or patch recompiles only the files that changed; optionally add ccache. Checking it
   needs one full kernel rebuild.

6. **Make QEMU useful for development — parked.**
   Finish setup, reach the desktop and verify network access. Check that the VM can restart
   without losing Android data. See [QEMU](specs/qemu.md) and [security](specs/security.md).

7. **Hardware enablement and performance tuning — deferred.**
   Brightness, MSI Bluetooth, headphones, HDMI audio, suspend and remaining regression checks
   stay in the component specs. Do not pursue them or speculative optimizations unless daily use
   exposes a practical problem or the owner resumes the work. For a new build, the owner runs
   `make update-usb` and retrieves logs if needed. Measure any actual bottleneck before
   changing its implementation; see [laptop hardware](specs/laptop-hardware.md) and
   [graphics](specs/graphics.md).

## How we track progress

- Work through one review step at a time so the build stays understandable.
- Use the component specs for detailed status; update this plan only when priorities or phases change.
- Choose tests and builds that fit the change. Do not rerun a full QEMU boot for documentation edits.

## Not a current goal

KernelSU/root, dual boot and public release infrastructure. The existing owner-run USB flasher
is not an internal-disk installer. New laptops need evidence-driven bring-up, not blanket hardware
support claims. Share clear, useful findings upstream where practical.
