# Security services

**Status:** working (software keys) — KeyMint and Gatekeeper run; storage encryption works.
**Last verified:** 2026-10-31 — `make qemu-check`: stable KeyMint/Gatekeeper PIDs, encrypted userdata mounted, SELinux enforcing.

## Goal
Provide the key and lock-screen services Android requires to boot, without the Googlebook
security chip or Trusty VM that QEMU cannot provide — and without weakening SELinux.

## Current state
Verified: software KeyMint and Gatekeeper from Google's Android 17 emulator image run unmodified;
vold unlocks file-based encryption; boot completes; SELinux enforcing.
Not verified: SetupWizard lock-screen setup, Google account sign-in, Play Integrity.
Not provided: hardware-backed keys, attestation, rollback resistance (Android falls back to
non-rollback-resistant keys, as expected). This is a development device, not a secure one.

## Decisions
- Emulator binaries are pinned by SHA-256 and copied **unmodified** with their missing library
  dependencies; Gatekeeper's executable is renamed to the standard service name, bytes unchanged.
- Donor and target are both API 37; extraction refuses a mismatch.
- Trusty security VM, remote key provisioning, Google security-chip daemon (gscd) and StrongBox
  are disabled; their HAL declarations are removed. Unrelated declarations stay.
- Firmware updaters and OTA are removed. The only firmware command left is a source-built
  `crossystem` stand-in that accepts the boot HAL's success values and rejects everything else.
- No SELinux permissive domains or broad policy changes.

## Files
- [scripts/emulator.sh](../../scripts/emulator.sh) — extract emulator files without mounts.
- [tools/android_overlay.py](../../tools/android_overlay.py) — `vendor()`/`system_ext()` install, remove and declare services.
- [android/gatekeeper.rc](../../android/gatekeeper.rc), [android/dali-qemu.rc](../../android/dali-qemu.rc) — service definitions and VM properties.
- [android/crossystem-qemu.c](../../android/crossystem-qemu.c) — firmware-command stand-in.
- [android/bootconfig.txt](../../android/bootconfig.txt) — StrongBox disabled.

## Verify
`make qemu-check JOBS=12` checks KeyMint (`android.hardware.security.keymint-service`) and
Gatekeeper (`android.hardware.gatekeeper-service`) keep the same PID for 30 seconds.

## Pitfalls
- Stock KeyMint waits for Trusty; vold then stalls and boot never completes.
- SELinux hides `init.svc.vendor.keymint-default` from the serial shell; check process PIDs instead.
- Unresolved library dependencies (other than LLNDK) fail the build; don't silence that.

## Actions
- [ ] Confirm SetupWizard and lock-screen PIN creation work with software Gatekeeper —
  done when a PIN is set and survives a reboot (tracked with [qemu.md](qemu.md) setup action).

## Handoff log
- 2026-10-31 `56719c0` — Software KeyMint/Gatekeeper from the emulator; Trusty/RKP/gscd disabled; boot completes.
