# OS image and disk

**Status:** working — declared change lists and patches, verified rebuilds, data-preserving updates.
**Last verified:** 2026-11-01 — `make test` (24 tests); a recreated `out/android/disk.img` differs from
the previous disk's table only by the missing `KERN-A` and the larger EFI-SYSTEM; 25 partitions are
byte-identical to Google's; `fsck.vfat` is clean on the ESP; a second `make android-image` wrote
nothing; `make qemu-check` passed (logs in `out/m1-validation/`).
2026-10-31 — all three partitions rebuilt with LZ4HC level 9 and fit; repeat rebuilds
byte-identical; a no-op build (about 10 s) preserved output timestamps and wrote no partitions.

## Goal
Turn Google's read-only recovery image into a private QEMU disk with a short list of explicit
changes, and update only the changed OS partitions without touching Android's data.

## Current state
Verified: `system_a`, `vendor_a`, `system_ext_a` rebuilt as EROFS with every file's bytes,
mode, owner, xattrs and SELinux label checked; development `vbmeta_a` from `avbtool`; disk
`out/android/disk.img` with a 32 GiB sparse userdata and a 576 MiB FAT32 EFI-SYSTEM (`DALI-BOOT`,
empty, Google's PARTUUID); updates copy only changed partitions
with read-back hashes; unchanged builds write nothing; updates refuse to run while the VM holds the disk lock.
Not verified: writing any of this to a real disk or USB (deliberately not done), and whether UEFI
firmware accepts the FAT32 partition (the UEFI boot test in [laptop-hardware.md](laptop-hardware.md)).

## Decisions
- Change Google's files only through the change directory of each partition,
  `android/<partition>/`, applied by [scripts/android-overlay.sh](../../scripts/android-overlay.sh):
  `remove.list` (each path must exist), `install.list` (path, mode, owner, SELinux type, source),
  then `*.patch` (unified diffs of Google's text files, header says why). A replaced file is removed,
  then installed. **No byte-offset edits and no change logic in Python.**
- Patches are applied to copies and written back in place, so patched files keep their owner,
  mode and SELinux label. Every file in a change directory must be used (`make test` checks).
- Reject symlinked parents before removing, installing or patching files; a patch target must
  itself be a regular file, not a symlink. Readability refactors must retain these guards.
- The overlay script only applies changes; checks live elsewhere. Vendor programs we install may
  link only to vendor `lib64` or the platform LLNDK
  ([scripts/check-vendor-libs.sh](../../scripts/check-vendor-libs.sh), run by the vendor build).
- Rebuild without root: `fsck.erofs` extraction and `mkfs.erofs` under fakeroot; original UUID
  kept; output must not exceed the original partition size. LZ4HC level 9 with 256 KiB clusters:
  2–3x faster to build than level 12 and about 0.2% larger (system 1053 MB of 1134 MB).
- AVB is disabled through a new vbmeta (`--algorithm NONE --flags 3`); SELinux stays enforcing.
- The disk is a reflink copy of the recovery image with userdata moved to the end and grown;
  slot A marked bootable/successful. It holds Android's data, so it is **never recreated automatically**.
- EFI-SYSTEM absorbs the blank `KERN-A` beside it and is formatted FAT32 for the laptop's boot
  files; it keeps its PARTUUID, which the initrd uses to find the disk. The script refuses unless
  both partitions are adjacent and all zeros, so a newer Google image is never formatted over.
  QEMU's direct-kernel boot ignores it.
- The updater may write only `system_a`, `vendor_a`, `system_ext_a`, `vbmeta_a` — never
  userdata, metadata, the GPT or the dynamic-partition (liblp) metadata.
- Dependencies are per partition: `android/vendor/`, Mesa, emulator and crossystem rebuild vendor
  only; `android/system_ext/` rebuilds system_ext only.

## Files
- [android/system/](../../android/system/), [android/system_ext/](../../android/system_ext/), [android/vendor/](../../android/vendor/) — every change to Google's partitions.
- [scripts/android-overlay.sh](../../scripts/android-overlay.sh) — applies one change directory; format in its header.
- [scripts/check-vendor-libs.sh](../../scripts/check-vendor-libs.sh) — library check for vendor programs we install.
- [scripts/android-partition.sh](../../scripts/android-partition.sh), [tools/fs_metadata.py](../../tools/fs_metadata.py) — rebuild and full comparison.
- [scripts/android-disk.sh](../../scripts/android-disk.sh) — create the private disk once: data partition, FAT32 boot partition.
- [tests/test_android_disk.py](../../tests/test_android_disk.py) — its layout and refusals on a synthetic Google-shaped disk.
- [tools/android_sync.py](../../tools/android_sync.py), [tools/lp.py](../../tools/lp.py) — partition updates.
- [scripts/unpack.sh](../../scripts/unpack.sh) — Google image inventory (`out/google/inventory.txt`).

## Verify
`make test` (sync, lock and overlay tests in [tests/test_overlay.py](../../tests/test_overlay.py);
disk layout in [tests/test_android_disk.py](../../tests/test_android_disk.py)),
then `make android-image JOBS=12`. A second run
must print no partition writes and leave output timestamps unchanged.

## Pitfalls
- fakeroot does keep ownership and xattrs, but only because the comparison checks every entry;
  never weaken [tools/fs_metadata.py](../../tools/fs_metadata.py) to make a build pass.
- Logical partitions can span several extents; the updater handles multi-extent copies (tested).
- An interrupted update is fixed by rerunning `make android-image`, not by deleting the disk.
- Generate patches against Google's pristine file, not a previous build:
  `fsck.erofs --extract=DIR --xattrs out/google/super/<p>_a.img`, edit a copy, then
  `diff -u --label a/PATH --label b/PATH original edited`. Patches apply with `--fuzz=0`.
- `mkfs.vfat` sizes clusters from the whole disk file, not the partition: at 19 GiB it picks 16 KiB
  clusters (36,843 for 576 MiB), too few for FAT32, which UEFI firmware may then read as FAT16.
  The script passes `-s 8`; the test checks at least 65,525 clusters.

## Actions
_None agreed._ The USB version of this disk is tracked in [laptop-hardware.md](laptop-hardware.md).

## Handoff log
- 2026-11-01 (this commit) — EFI-SYSTEM now absorbs the blank `KERN-A` as a 576 MiB FAT32, guarded
  and tested. Recreated disk checked and booted in QEMU. Boot files go in next (laptop-hardware.md).
- 2026-10-31 `0a29643` — Partitions use LZ4HC level 9 instead of 12: system rebuild 25 s → 17 s,
  vendor 17 s → 8 s, about 0.2% larger; QEMU boot check passed.
- 2026-10-31 `c84f989` — Restored symlink guards lost in the overlay simplification; new tests
  reproduced four unsafe cases before the fix. All 22 tests now pass; fresh baseline/current
  builds are byte-identical and a second build writes nothing.
- 2026-10-31 `67098bc` — Explained partition packing and system paths; named the Makefile's
  partition stem explicitly. No runtime configuration changes.
- 2026-10-31 `441bad5` — Simplified remove/install/patch processing; moved vendor library checking
  into its own script and unused-file checking into tests. Symlink regression corrected above.
- 2026-10-31 `357470d` — Image changes are now lists and patches per partition, applied by android-overlay.sh; Python overlay removed. Rebuild matched the old one apart from the 3 patched text files.
- 2026-10-31 `56719c0` — Rootless EROFS rebuilds with full metadata comparison; per-partition dependencies.
- 2026-10-31 `2f02300` — Private disk and first boot from Google's partitions.
