# Security services

**Status:** working (software keys) — renamed policy enforcing; key services stable.
**Last verified:** 2026-11-04 — 20 selector/overlay tests, image ABI/metadata/kABI checks, and
enforcing QEMU boot. Live mountinfo shows Google's system crypto bound into Conscrypt.
Comparative performance and physical-laptop selection remain unverified.
[Evidence](../../out/httpengine-investigation/).

Earlier, 2026-11-04 — 246 tests, source-derived policy comparison (identity changes
only), image metadata checks and enforcing direct/UEFI QEMU pass. KeyMint/Gatekeeper PIDs stable;
renamed collectors persist logs and hardware snapshot without project-domain denials.
[Evidence](../../out/gbos-builder-validation/).

## Goal
Provide the key and lock-screen services Android requires to boot, without the Googlebook
security chip or Trusty VM that QEMU cannot provide — and without weakening SELinux.

## Current state
Verified: project-owned SELinux type names change to `gbos_builder_*` together with
their service labels and file/property contexts. Android patches are regenerated from Google's
originals; permissions and enforcing policy are unchanged. Renamed image runtime checks pass.
Not verified: hardware-only audio policy on the physical laptop after renaming.

Verified: software KeyMint and Gatekeeper from Google's Android 17 emulator image run unmodified;
vold unlocks file-based encryption; boot completes; SELinux enforcing.
Not verified: SetupWizard lock-screen setup, Google account sign-in, Play Integrity.
Not provided: hardware-backed keys, attestation, rollback resistance (Android falls back to
non-rollback-resistant keys, as expected). This is a development device, not a secure one.

Verified: the selector requires SHA-NI on every reported logical CPU; otherwise it selects the
portable pair. QEMU selected Google's libraries, and live mountinfo confirmed the Conscrypt bind.
Not verified: stock-versus-portable performance or physical-laptop selection.

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
- SELinux remains enforcing; the crypto selector adds init file-mount access for the
  platform/vendor library types it needs to overlay.
- Keep Google's system/vendor BoringSSL when every logical CPU advertises SHA-NI; otherwise
  init binds the ABI-checked runtime-dispatched pair over both libraries before zygote.
  HttpEngine keeps its separate exact-ABI build over Tethering's crypto file. Both signed APEXes
  remain unchanged. Wi-Fi and other APEX copies are untouched. The stock path is verified in QEMU;
  comparative performance on SHA-NI hardware is not measured.

## Files
- [scripts/emulator.sh](../../scripts/emulator.sh) — extract emulator files without mounts; API check.
- [android/vendor/install.list](../../android/vendor/install.list), [android/vendor/remove.list](../../android/vendor/remove.list) — services installed and removed.
- [android/system_ext/crypto-select.sh](../../android/system_ext/crypto-select.sh) — selects stock or portable system/vendor crypto before APEX overlays.
- [android/system_ext/vintf-manifest.patch](../../android/system_ext/vintf-manifest.patch) — Trusty-only HAL declarations removed.
- [android/vendor/gatekeeper.rc](../../android/vendor/gatekeeper.rc), [android/system_ext/gbos-builder.rc](../../android/system_ext/gbos-builder.rc) — software-security services shared by QEMU and the laptop.
- [android/crossystem-qemu.c](../../android/crossystem-qemu.c) — firmware-command stand-in.
- [android/bootconfig.txt](../../android/bootconfig.txt) — StrongBox disabled.

## Verify
`make qemu-check` checks KeyMint (`android.hardware.security.keymint-service`) and
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
- 2026-11-04 (this commit) — 20 selector/overlay tests, image ABI/metadata/kABI checks and
  enforcing QEMU boot pass; live mountinfo confirms Google's system crypto is bound into Conscrypt.
  Comparative performance and physical-laptop selection remain unverified.
- 2026-11-04 (this commit) — Owner accepts Lenovo hardware test; saved `193204` logs have no
  HttpEngine trap samples. Remaining sampled SHA is in Bluetooth crypto, not replaced here.
  Dedicated HttpEngine HTTP/TLS request and MSI regression remain unverified.
- 2026-11-04 (this commit) — HttpEngine: exact 323-symbol ABI, 29 focused tests, image metadata,
  enforcing QEMU boot/mount propagation and native library/SHA/refcount probe pass.
  No new policy permission; actual HttpEngine requests and hardware regression unverified.
- 2026-11-04 (this commit) — Lenovo owner confirms faster Chrome with portable crypto;
  new saved logs show no earlier Conscrypt trap storm or detected crypto loader/integrity errors.
  Remaining HttpEngine/other-APEX emulation unchanged; MSI crypto regression untested.
- 2026-11-04 uncommitted — ABI-checked portable crypto integrated into system/vendor/Conscrypt.
  66 focused tests; enforcing QEMU mount hashes/namespaces, integrity/self-tests and local HTTPS
  pass; hardware CPU/app/Wi-Fi/Bluetooth regression pending. Other APEX crypto remains unchanged.
- 2026-11-04 (this commit) — Rename policy identifiers/init filename and regenerate Android
  patches; permission comparison unchanged. Enforcing direct/UEFI runs keep key services stable
  and save renamed logs with no project-domain denials. Hardware-only audio policy untested.
- 2026-11-02 (this commit) — Removed `gscutil.rc`; the laptop and QEMU logs both showed init
  blocked 10 s on `wait /dev/tpm0`. QEMU `boot_completed` 59.7 s → 49.9 s; setup screen inspected.
- 2026-11-02 (this commit) — Disabled `udsattestation` and the face feature. QEMU kernel log:
  IGsc start requests 389 → 0, face IVirtualHal 356 → 0; KeyMint/Gatekeeper PIDs stable, enforcing.
- 2026-11-01 (this commit) — Common security settings moved to `dali.rc` (pre-rename); graphics profiles are
  separate. The AMD-candidate image still has stable KeyMint/Gatekeeper PIDs and enforcing
  SELinux in the UEFI graphical check; no new policy permissions.
- 2026-10-31 `357470d` — Security changes moved to android/vendor/ lists and the system_ext VINTF patch; donor API check moved to emulator.sh.
- 2026-10-31 `56719c0` — Software KeyMint/Gatekeeper from the emulator; Trusty/RKP/gscd disabled; boot completes.
