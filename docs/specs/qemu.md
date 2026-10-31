# QEMU VM

**Status:** parked — boots to the setup screen with keyboard and mouse; setup not finished, paused while the laptop comes first.
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
- ACPI S3/S4 disabled: Android's idle suspend otherwise stops the display and serial shell
  (not enough on its own: see the s2idle pitfall).
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
- After about 3 minutes idle the guest still enters s2idle (`PM: suspend entry (s2idle)` in
  `out/qemu/kernel.log`): the serial shell stops answering and QMP `system_wakeup` fails ("not
  suspended"). `system_powerdown` (the ACPI button) wakes it. To stop a frozen VM, send QMP
  `quit` (`qmp()` in [android_smoke.py](../../tools/android_smoke.py)); it ends the guest without a shutdown.

## Actions
Parked while the laptop is the focus (owner, 2026-10-31); these are still the agreed QEMU steps.
- [ ] Finish SetupWizard in the VM — done when the desktop/launcher is reached and survives a
  reboot; record which steps were skipped (e.g. network, account).
- [ ] Verify networking — done when DNS and an HTTPS request work from the guest.
- [ ] Decide how to quiet Bluetooth crash loops (disable the services vs. a virtual device) — done
  when an approach is agreed.

### Ideas (not approved)
- Smoke check that also drives input (click through the welcome screen) automatically.
- Audio device for the VM.
- Keep the guest awake (for example Android's stay-awake setting) so it does not enter s2idle.

## Handoff log
- 2026-10-31 (this commit) — Parked: the owner is satisfied that QEMU boots Android to setup and
  moved to the laptop. Recorded that the guest enters s2idle after about 3 minutes idle.
- 2026-10-31 `56719c0` — Graphical boot to setup; mouse input; sleep disabled; bounded smoke check.
- 2026-10-31 `2f02300` — Headless boot to a serial shell (stalled at vold before software KeyMint).
