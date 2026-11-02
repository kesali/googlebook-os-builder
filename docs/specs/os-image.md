# OS image and disk

**Status:** working — declared change lists and patches, verified rebuilds, data-preserving updates.
**Last verified:** 2026-11-01 — diagnostic image rebuilt with full filesystem metadata checks;
51,657,060,352 bytes outside system/vendor/system_ext are unchanged, including userdata,
metadata, GPT/liblp and ESP ([comparison](../../out/bootlog-validation/preservation-final.txt)).
A no-op takes 22.4 s, writes nothing and preserves nanosecond timestamps of nine published
outputs ([log](../../out/bootlog-validation/noop-final.log),
[timestamps](../../out/bootlog-validation/noop-timestamps.txt)).
Earlier: AMD image rebuilt with full metadata checks; all 52,168,658,944
bytes outside vendor, system_ext, vendor_dlkm and ESP match the baseline, including userdata,
metadata and GPT/liblp tables. No-op build: 16 s, no writes, all 25 checked output timestamps
unchanged ([evidence](../../out/overnight/preservation.log), [no-op](../../out/overnight/noop-final.log)).
Earlier: `make test` (40 tests); a recreated `out/android/disk.img` differs from
the previous disk's table only by the missing `KERN-A` and the larger EFI-SYSTEM; 25 partitions are
byte-identical to Google's; with the boot files written, `fsck.vfat` is clean on the ESP, a second
`make android-image` wrote nothing, the bytes outside the ESP were unchanged and `make qemu-check`
passed (logs in `out/m1-validation/`).
2026-10-31 — all three partitions rebuilt with LZ4HC level 9 and fit; repeat rebuilds
byte-identical; a no-op build (about 10 s) preserved output timestamps and wrote no partitions.

## Goal
Turn Google's read-only recovery image into a private QEMU disk with a short list of explicit
changes, and update only the changed OS partitions without touching Android's data.

## Current state
Verified: `system_a`, `vendor_a`, `system_ext_a`, `vendor_dlkm_a` rebuilt as EROFS with every file's bytes,
mode, owner, xattrs and SELinux label checked; development `vbmeta_a` from `avbtool`; disk
`out/android/disk.img` with a 32 GiB sparse userdata and a 576 MiB FAT32 EFI-SYSTEM (`DALI-BOOT`,
Google's PARTUUID) holding the laptop's boot files; updates copy only changed partitions
with read-back hashes; unchanged builds write nothing; updates refuse to run while the VM holds the disk lock.
OVMF reads the FAT32 ESP and Android finds its partitions over USB (`make android-uefi-check`,
2026-11-01; [laptop-hardware.md](laptop-hardware.md)). Its disposable boots left the source disk
byte-identical. The laptop spec records a physical USB transfer/read-back and failed Android
boots; a usable physical screen remains unverified ([laptop-hardware.md](laptop-hardware.md)).
The system/system_ext logging changes and removal of vendor's precompiled policy are built
and verified through three disposable UEFI boots ([boot.md](boot.md)). Android data/layout
remain unchanged; this diagnostic candidate has not been transferred to the physical USB.

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
  Exception: vendor_dlkm uses Zstd level 9, 17,190,912 B within its 18,096,128 B partition.
  LZ4 required 25.6 MB with AMD; Zstd retains every Google module and the fixed layout.
- AVB is disabled through a new vbmeta (`--algorithm NONE --flags 3`); SELinux stays enforcing.
- The disk is a reflink copy of the recovery image with userdata moved to the end and grown;
  slot A marked bootable/successful. It holds Android's data, so it is **never recreated automatically**.
- EFI-SYSTEM absorbs the blank `KERN-A` beside it and is formatted FAT32 for the laptop's boot
  files; it keeps its PARTUUID, which the initrd uses to find the disk. The script refuses unless
  both partitions are adjacent and all zeros, so a newer Google image is never formatted over.
  QEMU's direct-kernel boot ignores it.
- The boot files go into that partition with mtools, never a mount or loop device
  ([scripts/android-boot.sh](../../scripts/android-boot.sh)), and only when the partition is
  the FAT32 labelled `DALI-BOOT`. `EFI/` and `dali/` are replaced as a whole and read back; if
  they already match, nothing is written. Only these two trees are touched.
- The updater may write only `system_a`, `vendor_a`, `system_ext_a`, `vendor_dlkm_a`, `vbmeta_a` — never
  userdata, metadata, the GPT or the dynamic-partition (liblp) metadata.
- Dependencies are per partition: Mesa, minigbm, firmware, emulator and crossystem rebuild vendor
  only; system_ext changes rebuild system_ext; the signed module manifest rebuilds vendor_dlkm.

## Files
- [android/system/](../../android/system/), [android/system_ext/](../../android/system_ext/), [android/vendor/](../../android/vendor/) — every change to Google's partitions.
- [android/vendor_dlkm/](../../android/vendor_dlkm/), [tools/laptop_module_check.py](../../tools/laptop_module_check.py) — new signed modules, dependencies and laptop alias checks.
- [scripts/android-overlay.sh](../../scripts/android-overlay.sh) — applies one change directory; format in its header.
- [scripts/check-vendor-libs.sh](../../scripts/check-vendor-libs.sh) — library check for vendor programs we install.
- [scripts/android-partition.sh](../../scripts/android-partition.sh), [tools/fs_metadata.py](../../tools/fs_metadata.py) — rebuild and full comparison.
- [scripts/android-disk.sh](../../scripts/android-disk.sh) — create the private disk once: data partition, FAT32 boot partition.
- [tests/test_android_disk.py](../../tests/test_android_disk.py) — its layout and refusals on a synthetic Google-shaped disk.
- [scripts/android-boot.sh](../../scripts/android-boot.sh), [tests/test_android_boot.py](../../tests/test_android_boot.py) — boot files into the FAT32 partition; its refusals, no-op and repair on a synthetic disk.
- [tools/android_sync.py](../../tools/android_sync.py), [tools/lp.py](../../tools/lp.py) — partition updates.
- [scripts/unpack.sh](../../scripts/unpack.sh) — Google image inventory (`out/google/inventory.txt`).

## Verify
`make test` (sync, lock and overlay tests in [tests/test_overlay.py](../../tests/test_overlay.py);
disk layout in [tests/test_android_disk.py](../../tests/test_android_disk.py); boot files in
[tests/test_android_boot.py](../../tests/test_android_boot.py)),
then `make android-image JOBS=12`. A second run
must print no partition or boot-file writes and leave output timestamps unchanged.

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
- 2026-11-01 `uncommitted` — Declared native boot-log services and scoped platform policy;
  rebuilt metadata checks, unaffected-byte comparison and no-op timestamp/write checks pass.
  Three disposable UEFI boots pass; physical transfer remains the owner's next step.
- 2026-11-01 (this commit) — AMD userspace/firmware and signed vendor_dlkm modules added through
  declarative overlays. Zstd fits without removing Google drivers. Full filesystem metadata,
  unaffected disk bytes and unchanged-build publication verified; 59 unit tests pass.
- 2026-11-01 (this commit) — OVMF/GRUB read the ESP and Android mounts USB partitions in the
  disposable UEFI test. Corrected the menu's screen-console selection; bytes outside the ESP
  matched the earlier disk, and the boot tests left their source image unchanged.
- 2026-11-01 `deee56b` — `make android-image` also writes the boot files into the ESP
  (`android-boot.sh`, mtools, whole-tree replace, no-op when equal); real-disk run checked, neighbours
  unchanged, `make qemu-check` passes. UEFI/laptop use is tracked in laptop-hardware.md.
- 2026-11-01 `4811074` — EFI-SYSTEM now absorbs the blank `KERN-A` as a 576 MiB FAT32, guarded
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
