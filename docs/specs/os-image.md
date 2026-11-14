# OS image and disk

**Status:** partial — compact image build, metadata checks and direct QEMU pass;
fresh physical installation and USB update remain unverified.
**Last verified:** 2026-11-07 — image checks and enforcing QEMU pass.

## Goal
Build a private Android disk from Google's recovery image and update only declared OS
partitions without overwriting user data.

## Current state
The build produces a compact GPT image with an A-only Android layout, a FAT32 boot
partition, a diagnostic-log partition and userdata. Image updates preserve the disk
layout and userdata. The owner-run fresh installer is destructive to its selected USB;
no physical disk is written by the build or validation agent.

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
- Keep SELinux enforcing. Diagnostic logs use the dedicated FAT32 partition and are
  unencrypted.

## Files
- [tools/android_fresh.py](../../tools/android_fresh.py) — guarded image creation.
- [tools/android_disk.py](../../tools/android_disk.py) and
  [android/super-layout.json](../../android/super-layout.json) — disk and logical layout.
- [tools/update_usb.py](../../tools/update_usb.py) and
  [tools/install_usb.py](../../tools/install_usb.py) — owner-run USB update/install.
- [scripts/android-overlay.sh](../../scripts/android-overlay.sh) — apply declared changes.
- [tools/fs_metadata.py](../../tools/fs_metadata.py) — filesystem metadata checks.

## Verify
Run `make test` and `make android-image`. Repeat the image build and confirm it writes
no partitions or boot files and preserves output timestamps. Use disposable QEMU copies
for boot checks; never write physical media during validation.

## Pitfalls
- `ANDROID_DATA_GIB` affects only new images; it does not shrink existing userdata.
- Never weaken metadata, symlink, partition-fit, recovery-hash or USB identity checks.
- Generate patches against Google's pristine files and apply them without fuzz.
- An interrupted image update is repaired by rerunning `make android-image`; do not
  delete the disk or editable source trees.

## Actions
- [ ] Owner tests fresh installation and update — done when a fresh USB reaches setup,
  the updater succeeds on the matching layout, user data is preserved by an ordinary
  update, and a repeat makes no writes.
