# OS image and disk

**Status:** partial — the integrated overlay passes the mandatory setup OTA gate in QEMU;
complete setup and physical installation remain unverified.
**Last verified:** 2026-11-15 — a fresh disposable QEMU disk reached user selection after
Google reported an OTA available; Play early update completed and SELinux was enforcing.

## Goal
Build a private Android disk from Google's recovery image and update only declared OS
partitions without overwriting user data.

## Current state
The build produces a compact GPT image with an A-only Android layout, a FAT32 boot
partition, a journaled ext4 diagnostic-log partition and userdata. Image updates preserve the
disk layout and userdata. The owner-run fresh installer is destructive to its selected USB;
no physical disk is written by the build or validation agent.

Google's setup requires an OTA even though this image has no compatible update engine.
A preinstalled resource overlay routes that result to the existing early-update step without
changing Google's APK. The integrated image passed the OTA gate on a disposable QEMU disk;
finishing setup and physical hardware remain unverified.

## Decisions
- Pin and verify the recovery image before extraction. Apply Google image changes only
  through `android/<partition>/` lists and source-derived text patches.
- Build EROFS without root and compare file bytes, metadata and SELinux labels. Enforce
  declared partition sizes and preserve Google kernel ABI checks.
- Never recreate an existing disk image automatically. Generate fresh images at a
  separate path; Android userdata contains persistent data.
- The normal updater may change only `system_a`, `vendor_a`, `system_ext_a`,
  `vendor_dlkm_a`, `vbmeta_a` and managed boot files. It must preserve userdata,
  metadata, GPT and liblp metadata.
- Require explicit USB selection, identity/layout checks, default-no confirmation and
  read-back. The full installer is a separate, destructive owner action.
- Keep SELinux enforcing. Diagnostic logs use the dedicated ext4 partition and are
  unencrypted.

## Files
- [tools/android_fresh.py](../../tools/android_fresh.py) — guarded image creation.
- [tools/android_disk.py](../../tools/android_disk.py) and
  [android/super-layout.json](../../android/super-layout.json) — disk and logical layout.
- [tools/update_usb.py](../../tools/update_usb.py) and
  [tools/install_usb.py](../../tools/install_usb.py) — owner-run USB update/install.
- [scripts/android-overlay.sh](../../scripts/android-overlay.sh) — apply declared changes.
- [scripts/setup-overlay.sh](../../scripts/setup-overlay.sh) — build the signed setup overlay.
- [tools/fs_metadata.py](../../tools/fs_metadata.py) — filesystem metadata checks.

## Verify
Run focused tests, `make android-image` and `make qemu-check`. Repeat the image build and
confirm it writes no partitions or boot files and preserves output timestamps. Use a fresh
disposable QEMU disk to check the setup OTA path; never write physical media during validation.

## Pitfalls
- `ANDROID_DATA_GIB` affects only new images; it does not shrink existing userdata.
- Fresh installation is not a secure erase; old data may remain recoverable.
- Updates preserve the diagnostic partition. A fresh USB installation copies the source
  image's filesystem, so an older FAT32 source image must be replaced with a separately
  created ext4 image before installation. Preserve the existing image and its userdata.
- Never weaken metadata, symlink, partition-fit, recovery-hash or USB identity checks.
- Generate patches against Google's pristine files and apply them without fuzz.
- Preserve `out/setup-overlay-key/` privately across builds and USB updates. Losing its
  signing key can prevent an installed overlay from being updated; never commit the key.
- An interrupted image update is repaired by rerunning `make android-image`; do not
  delete the disk or editable source trees.

## Actions
- [ ] Verify complete setup — done when setup completes and Play app updates work on
  physical hardware.
- [ ] Owner tests fresh installation and update — done when a fresh USB reaches setup,
  the updater succeeds on the matching layout, user data is preserved by an ordinary
  update, and a repeat makes no writes.
