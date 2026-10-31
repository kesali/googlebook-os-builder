# OS image and disk

**Status:** working — explicit file-level changes, verified rebuilds, data-preserving updates.
**Last verified:** 2026-10-31 — full rebuild compared every file's bytes and metadata; no-op build wrote nothing; running VM blocked updates.

## Goal
Turn Google's read-only recovery image into a private QEMU disk with a short list of explicit
changes, and update only the changed OS partitions without touching Android's data.

## Current state
Verified: `system_a`, `vendor_a`, `system_ext_a` rebuilt as EROFS with every file's bytes,
mode, owner, xattrs and SELinux label checked; development `vbmeta_a` from `avbtool`; disk
`out/android/disk.img` with a 32 GiB sparse userdata; updates copy only changed partitions
with read-back hashes; unchanged builds write nothing; updates refuse to run while the VM holds the disk lock.
Not verified: writing any of this to a real disk or USB (deliberately not done).

## Decisions
- Change Google's files only through [tools/android_overlay.py](../../tools/android_overlay.py):
  whole files added, removed or replaced, settings edited in place. **No byte-offset edits.**
- Rebuild without root: `fsck.erofs` extraction and `mkfs.erofs` under fakeroot; original UUID
  kept; output must not exceed the original partition size.
- AVB is disabled through a new vbmeta (`--algorithm NONE --flags 3`); SELinux stays enforcing.
- The disk is a reflink copy of the recovery image with userdata moved to the end and grown;
  slot A marked bootable/successful. It holds Android's data, so it is **never recreated automatically**.
- The updater may write only `system_a`, `vendor_a`, `system_ext_a`, `vbmeta_a` — never
  userdata, metadata, the GPT or the dynamic-partition (liblp) metadata.
- Dependencies are per partition: Mesa/security/property changes rebuild vendor only; the VM
  init script rebuilds system_ext only.

## Files
- [tools/android_overlay.py](../../tools/android_overlay.py) — every change to Google's partitions.
- [scripts/android-partition.sh](../../scripts/android-partition.sh), [tools/fs_metadata.py](../../tools/fs_metadata.py) — rebuild and full comparison.
- [scripts/android-disk.sh](../../scripts/android-disk.sh) — create the private disk once.
- [tools/android_sync.py](../../tools/android_sync.py), [tools/lp.py](../../tools/lp.py) — partition updates.
- [scripts/unpack.sh](../../scripts/unpack.sh) — Google image inventory (`out/google/inventory.txt`).

## Verify
`make test` (sync, overlay and lock tests), then `make android-image JOBS=12`. A second run
must print no partition writes and leave output timestamps unchanged.

## Pitfalls
- fakeroot does keep ownership and xattrs, but only because the comparison checks every entry;
  never weaken [tools/fs_metadata.py](../../tools/fs_metadata.py) to make a build pass.
- Logical partitions can span several extents; the updater handles multi-extent copies (tested).
- An interrupted update is fixed by rerunning `make android-image`, not by deleting the disk.

## Actions
_None agreed._

### Ideas (not approved)
- Writing the same partitions to a USB or internal disk for the laptop — see [laptop-hardware.md](laptop-hardware.md).

## Handoff log
- 2026-10-31 `56719c0` — Rootless EROFS rebuilds with full metadata comparison; per-partition dependencies.
- 2026-10-31 `2f02300` — Private disk and first boot from Google's partitions.
