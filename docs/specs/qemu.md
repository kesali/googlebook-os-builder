# QEMU VM

**Status:** parked — direct graphical boot and softpipe pass; SetupWizard and guest
networking are not complete.
**Last verified:** 2026-11-07 — `make qemu-check` passes on the pinned recovery image.

## Goal
Provide a safe, repeatable graphical development VM and a bounded boot regression check.

## Current state
QEMU runs the private NVMe disk with KVM, VNC on localhost, virtio input, serial shell
and QMP. The bounded check verifies boot completion, stable services, enforcing SELinux
and softpipe. The screenshot must be inspected; setup has not been completed. Input and
USB-UEFI were not checked on the latest image. Network access beyond DHCP, Google sign-in
and apps remain unverified.

## Decisions
- Run QEMU inside the builder; publish VNC only on `127.0.0.1`.
- Use `virtio-mouse-pci`; Android treats a virtio tablet as an internal touchscreen.
- Use `-no-reboot` and a shared disk lock so failures stop and updates cannot write a
  running VM disk.
- Disable ACPI S3/S4. The guest may still enter s2idle; use QMP `quit` if it stops
  responding.
- Keep the QEMU softpipe profile's boot-animation and shader-priming skips; do not apply
  them to the laptop.

## Files
- [scripts/qemu.sh](../../scripts/qemu.sh) — VM lifecycle.
- [tools/android_smoke.py](../../tools/android_smoke.py) — `make qemu-check`.
- [tools/android_console.py](../../tools/android_console.py) — serial commands.
- [config.mk](../../config.mk) — VM resources and port.

## Verify
Run `make qemu-check`, inspect `out/qemu/screen.png`, and confirm the VM exits. Verify
input separately with `make qemu` and a VNC viewer.

## Pitfalls
- A correctly sized screenshot may still be QEMU's inactive-display placeholder.
- Serial shell checks may not read SELinux-protected service properties; check PIDs.
- Unbounded `logcat -b all -d` can wedge the serial shell; filter on the guest.
- After s2idle, `system_powerdown` may wake the guest; QMP `quit` stops it safely.

## Actions
- [ ] Finish SetupWizard — done when the desktop is reached and survives reboot.
- [ ] Verify networking — done when guest DNS and an HTTPS request succeed.
