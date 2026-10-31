# QEMU VM

**Status:** partial — boots to the setup screen with keyboard and mouse; setup not finished.
**Last verified:** 2026-10-31 — `make qemu-check`; VNC mouse click reached the language picker (`out/qemu/input-screen.png`).

## Goal
A fast, safe place to develop Googlebook OS: one command builds what changed and boots it,
with a screen, input, network and a shell, and a bounded check that proves a real boot.

## Current state
Verified: KVM VM (`-cpu host`, 4 CPUs, 6 GB, q35) boots the private NVMe disk; VNC on
localhost:5900; virtio keyboard and relative mouse; virtual Ethernet gets `10.0.2.15/24`;
serial shell and QMP via Unix sockets; clean guest shutdown.
Not verified: finishing SetupWizard, Internet access beyond DHCP, Google sign-in, apps.
Known noise: Bluetooth services crash-loop because no Bluetooth device exists.

## Decisions
- QEMU runs inside the builder container; VNC is published on host `127.0.0.1` only.
- Relative `virtio-mouse-pci`, not `virtio-tablet-pci` — Android treated the tablet as an
  internal touchscreen and clicks never landed.
- ACPI S3/S4 disabled: Android's idle suspend otherwise stops the display and serial shell.
- `-no-reboot`: a guest reboot or panic ends QEMU instead of looping.
- A shared lock on the disk: the updater refuses to write while the VM runs.

## Files
- [scripts/qemu.sh](../../scripts/qemu.sh) — the virtual machine.
- [tools/android_smoke.py](../../tools/android_smoke.py) — `make qemu-check`; `qmp()` helper for screenshots and input.
- [tools/android_console.py](../../tools/android_console.py) — `make console COMMAND='...'`.
- [config.mk](../../config.mk) — CPUs, memory, data size, VNC port.

## Verify
`make qemu-check JOBS=12` requires: boot completed, boot animation gone, stable system_server/
SurfaceFlinger/KeyMint/Gatekeeper PIDs for 30 s, SELinux enforcing, softpipe, 1280x720 scanout.
Evidence in `out/qemu/`. Then **look at `screen.png`**. For input, use `make qemu` + a VNC viewer.

## Pitfalls
- `sys.boot_completed=1` arrives while the boot animation is still on screen; wait for it to exit.
- A 1280x720 screenshot can still be QEMU's inactive-display placeholder; inspect it.
- Unbounded `logcat -b all -d` over serial can time out and leave the shell busy; filter on the
  guest (`logcat -d -s Tag | tail -n 200`). Ctrl-C through the socket recovers it.
- Serial-shell checks can't read some `init.svc.*` properties (SELinux); check PIDs instead.
- Software rendering plus instruction emulation makes first boot take several minutes.

## Actions
- [ ] Finish SetupWizard in the VM — done when the desktop/launcher is reached and survives a
  reboot; record which steps were skipped (e.g. network, account).
- [ ] Verify networking — done when DNS and an HTTPS request work from the guest.
- [ ] Decide how to quiet Bluetooth crash loops (disable the services vs. a virtual device) — done
  when an approach is agreed.

### Ideas (not approved)
- Smoke check that also drives input (click through the welcome screen) automatically.
- Audio device for the VM.

## Handoff log
- 2026-10-31 `56719c0` — Graphical boot to setup; mouse input; sleep disabled; bounded smoke check.
- 2026-10-31 `2f02300` — Headless boot to a serial shell (stalled at vold before software KeyMint).
