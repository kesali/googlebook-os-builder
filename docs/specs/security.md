# Security services

**Status:** working with software keys — KeyMint/Gatekeeper boot under enforcing SELinux;
hardware-backed keys and attestation are unavailable.
**Last verified:** 2026-11-07 — image and QEMU checks pass with stable software security
services; all BoringSSL exports match.

## Goal
Provide Android's required key and lock-screen services without the unavailable security
chip or Trusty VM, while keeping SELinux enforcing.

## Current state
Software KeyMint and Gatekeeper from Google's Android 17 emulator image run unmodified;
vold unlocks file-based encryption. Portable BoringSSL is ABI-checked and installed for
the system/vendor consumers. Hardware-backed keys, attestation and rollback resistance
are not provided. SetupWizard PIN creation, account sign-in and Play Integrity are
unverified.

## Decisions
- Pin emulator binaries and copy them unmodified with required libraries. Require donor
  and target API levels to match.
- Disable Trusty-only security services, StrongBox and unavailable face hardware; leave
  unrelated service declarations unchanged.
- Keep SELinux enforcing. Do not add broad mount permissions or weaken policy to make
  crypto overlays work.
- Install the ABI-checked portable BoringSSL pair without boot-time CPU selection.
  Keep HttpEngine's separate exact-ABI build and leave signed APEXes unchanged.
- Treat this as a development device, not a secure device: software keys lack hardware
  protection and rollback resistance.

## Files
- [scripts/emulator.sh](../../scripts/emulator.sh) — extract and API-check emulator files.
- [android/vendor/install.list](../../android/vendor/install.list) and
  [android/vendor/remove.list](../../android/vendor/remove.list) — service selection.
- [android/system/crypto.rc](../../android/system/crypto.rc) — crypto library overlays.
- [android/system_ext/vintf-manifest.patch](../../android/system_ext/vintf-manifest.patch) —
  remove unsupported Trusty declarations.
- [android/vendor/gatekeeper.rc](../../android/vendor/gatekeeper.rc) — software Gatekeeper.

## Verify
Run `make qemu-check`; KeyMint and Gatekeeper PIDs must remain stable and SELinux must
remain enforcing. Run the focused crypto/overlay tests when changing their inputs.

## Pitfalls
- Stock KeyMint waits for Trusty, which can stall vold and prevent boot.
- SELinux may hide service properties from the serial shell; verify process PIDs.
- Vendor binaries may link only to vendor libraries or LLNDK; keep the vendor-library
  check enabled.

## Actions
- [ ] Verify lock-screen PIN persistence — done when the owner sets a PIN in SetupWizard
  and confirms it survives reboot.
