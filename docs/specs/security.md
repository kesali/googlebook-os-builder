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
- Donor and target are both API 37; [scripts/emulator.sh](../../scripts/emulator.sh) refuses a mismatch.
- Trusty security VM, remote key provisioning, Google security-chip daemon (gscd), its UDS
  attestation client and StrongBox are disabled; their HAL declarations are removed. Unrelated
  declarations stay. The attestation client otherwise asked for gscd once a second forever.
- No face sensor: Google's face HAL APEX is removed and
  [no-face.xml](../../android/vendor/no-face.xml) marks the feature unavailable, so FaceService
  does not start and poll for its virtual test HAL once a second.
- Firmware updaters and OTA are removed. This includes the security-chip update at startup
  (`gscutil.rc`): init waited 10 s for a `/dev/tpm0` that the TPM blacklist keeps absent. The
  only firmware command left is a source-built `crossystem` stand-in that accepts the boot HAL's
  success values and rejects everything else.
- No SELinux permissive domains or broad policy changes.

## Files
- [scripts/emulator.sh](../../scripts/emulator.sh) — extract emulator files without mounts; API check.
- [android/vendor/install.list](../../android/vendor/install.list), [android/vendor/remove.list](../../android/vendor/remove.list) — services installed and removed.
- [android/system_ext/vintf-manifest.patch](../../android/system_ext/vintf-manifest.patch) — Trusty-only HAL declarations removed.
- [android/vendor/gatekeeper.rc](../../android/vendor/gatekeeper.rc), [android/system_ext/dali.rc](../../android/system_ext/dali.rc) — software-security services shared by QEMU and the laptop.
- [android/crossystem-qemu.c](../../android/crossystem-qemu.c) — firmware-command stand-in.
- [android/bootconfig.txt](../../android/bootconfig.txt) — StrongBox disabled.

## Verify
`make qemu-check JOBS=12` checks KeyMint (`android.hardware.security.keymint-service`) and
Gatekeeper (`android.hardware.gatekeeper-service`) keep the same PID for 30 seconds.

## Pitfalls
- Stock KeyMint waits for Trusty; vold then stalls and boot never completes.
- SELinux hides `init.svc.vendor.keymint-default` from the serial shell; check process PIDs instead.
- An installed program needing a library not in vendor `lib64` or the LLNDK fails the build;
  add the library to [android/vendor/install.list](../../android/vendor/install.list), don't silence the check.

## Actions
- [ ] Confirm SetupWizard and lock-screen PIN creation work with software Gatekeeper —
  done when a PIN is set and survives a reboot (tracked with [qemu.md](qemu.md) setup action).

## Handoff log
- 2026-11-02 (this commit) — Removed `gscutil.rc`; the laptop and QEMU logs both showed init
  blocked 10 s on `wait /dev/tpm0`. QEMU `boot_completed` 59.7 s → 49.9 s; setup screen inspected.
- 2026-11-02 (this commit) — Disabled `udsattestation` and the face feature. QEMU kernel log:
  IGsc start requests 389 → 0, face IVirtualHal 356 → 0; KeyMint/Gatekeeper PIDs stable, enforcing.
- 2026-11-01 (this commit) — Common security settings moved to `dali.rc`; graphics profiles are
  separate. The AMD-candidate image still has stable KeyMint/Gatekeeper PIDs and enforcing
  SELinux in the UEFI graphical check; no new policy permissions.
- 2026-10-31 `357470d` — Security changes moved to android/vendor/ lists and the system_ext VINTF patch; donor API check moved to emulator.sh.
- 2026-10-31 `56719c0` — Software KeyMint/Gatekeeper from the emulator; Trusty/RKP/gscd disabled; boot completes.
