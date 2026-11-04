# QEMU VM

**Status:** parked — gbos-builder screen/input regression verified; setup not finished.
**Last verified:** 2026-11-04 — Full recipe image: disposable direct boot passes stable PIDs,
enforcing SELinux and softpipe; setup and Accessibility after a tap inspected. Both USB-UEFI
runs pass, with inspected graphics setup/early DRM console and hidden unchanged NVMe decoy.
All VMs exited; final hashes/timestamps confirm source image unchanged.
[Evidence](../../out/full-hardware-recipes/).

Earlier, 2026-11-04 — New renamed image passes the existing bounded graphical
verifier through a session harness: stable system/graphics/key-service PIDs, SELinux enforcing,
softpipe, new collector domain and saved logs. Setup and Accessibility after an injected tap
are inspected. `make android-uefi-check` passes both runs with the NVMe decoy unchanged.
Optional renamed Berberis argument also checked. All test VMs exited.
[Evidence](../../out/gbos-builder-validation/).

Earlier, 2026-11-02 — `make qemu-check` PASS with `sys.boot_completed` at 20.5 s
(4 CPUs); [setup screen](../../out/qemu-boot-speed/qemu-check-screen.png) inspected. 2026-10-31: a
VNC mouse click reached the language picker (`out/qemu/input-screen.png`).

## Goal
A fast, safe place to develop Googlebook OS: one command builds what changed and boots it,
with a screen, input, network and a shell, and a bounded check that proves a real boot.

## Current state
Verified: gbos-builder build/boot identifiers and diagnostic path rename; runner and standalone
helpers use the new image path. Existing VM disks are preserved. Graphical/input checks pass above.

Verified: KVM VM (`-cpu host`, 4 CPUs, 6 GB, q35) boots the private NVMe disk; VNC on
localhost:5900; virtio keyboard and relative mouse; virtual Ethernet gets `10.0.2.15/24`;
serial shell and QMP via Unix sockets; clean guest shutdown. Boot completes in about 20 s
([timings](../../out/qemu-boot-speed/summary.txt)).
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
- The softpipe profile skips SurfaceFlinger's shader priming and the boot animation
  ([graphics-softpipe.rc](../../hardware/drivers/qemu-virtio/system_ext/graphics-softpipe.rc)): under softpipe they kept
  boot completion waiting for WindowManager's 30 s timeout (~49 s → ~22 s). The laptop keeps both.

## Files
- [scripts/qemu.sh](../../scripts/qemu.sh) — the virtual machine.
- [tools/android_smoke.py](../../tools/android_smoke.py) — `make qemu-check`; `qmp()` helper for screenshots and input.
- [tools/android_console.py](../../tools/android_console.py) — `make console COMMAND='...'`.
- [config.mk](../../config.mk) — CPUs, memory, data size, VNC port.

## Verify
`make qemu-check` requires: boot completed, boot animation gone, stable system_server/
SurfaceFlinger/KeyMint/Gatekeeper PIDs for 30 s, SELinux enforcing, softpipe, 1280x720 scanout.
Evidence in `out/qemu/`. Then **look at `screen.png`**. For input, use `make qemu` + a VNC viewer.

## Pitfalls
- `***** BOOT TIMEOUT: forcing display enabled` means WindowManager waited 30 s for a window or
  the boot animation. To see which, run `cmd protolog_configuration logcat enable WM_DEBUG_BOOT`
  over the console before `boot_progress_enable_screen`. The serial shell cannot read the result in
  `/metadata/gbos-builder-bootlog/current/android-boot.log*`; after the VM stops, copy the metadata partition
  out of `out/android/disk.img` and read it with `debugfs` ([boot spec](boot.md)).
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
- 2026-11-04 uncommitted — Full recipe image passes disposable direct/USB-UEFI checks;
  setup and direct Accessibility tap screenshots inspected. VMs exited; deliverable unchanged.
- 2026-11-04 uncommitted — Softpipe profile and first-stage module declarations moved into
  qemu-virtio recipe; contents/order intended unchanged. Validation deferred by the owner.
- 2026-11-04 (this commit) — Rename runner/console identities and standalone image defaults;
  no VM geometry or enforcement change. Direct/UEFI setup screens inspected, accessibility
  tap responds, saved diagnostics and Berberis selection checked. VMs exited; setup not completed.
- 2026-11-02 (this commit) — Softpipe profile skips shader priming and the boot animation; boot
  completes at ~20 s instead of ~50 s (WindowManager no longer hits its 30 s BOOT TIMEOUT).
- 2026-10-31 `9c78a5d` — Parked: the owner is satisfied that QEMU boots Android to setup and
  moved to the laptop. Recorded that the guest enters s2idle after about 3 minutes idle.
- 2026-10-31 `56719c0` — Graphical boot to setup; mouse input; sleep disabled; bounded smoke check.
- 2026-10-31 `2f02300` — Headless boot to a serial shell (stalled at vold before software KeyMint).
