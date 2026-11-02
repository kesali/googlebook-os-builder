# OS image and disk

**Status:** working — declared change lists and patches, verified rebuilds, data-preserving updates.
**Last verified:** 2026-11-02 — `make android-image JOBS=12` rebuilt only vendor (24 s) with zram
writeback off; a QEMU boot of it reached setup with SELinux enforcing and no 8 GiB writeback
device in the kernel log, where the previous vendor image had one
([evidence](../../out/data-growth-validation/)); `make test` passes 113 tests. Earlier the same day:
`make android-image JOBS=12` (54 s) rebuilt system, vendor, system_ext and vendor_dlkm; every
replaced Google file passed
[check-replacements.sh](../../scripts/check-replacements.sh) and the full metadata comparison;
the updater wrote only OS partitions. A repeat build took 16 s and left `disk.img` unmodified.
`make test` passes 106 unit tests; `make qemu-check` reaches setup
([screen](../../out/qemu/screen.png), inspected).
Earlier: all 52,168,658,944 bytes outside the updated partitions matched a preserved baseline,
including userdata, metadata and GPT/liblp
([comparison](../../out/hardware-fixes-validation/preservation-final.txt)).

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
byte-identical. The owner later completed physical setup with Wi-Fi and input on the prior image;
the current image has not been transferred to the USB ([laptop-hardware.md](laptop-hardware.md)).
The system/system_ext logging changes and removal of vendor's precompiled policy are built
and verified through the QEMU smoke test ([boot.md](boot.md)). The image updater changed only
the OS partitions named above; Android userdata, metadata and layout were preserved. The
QEMU test used a reflinked copy, and this candidate has not been transferred to the physical USB.

## Decisions
- Pin the local Google recovery image by SHA-256 in [config.mk](../../config.mk). Verify it before
  clearing or extracting `out/google`; alternate images must supply their own verified hash.
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
- A file listed in both `remove.list` and `install.list` replaces one of Google's and must be a
  drop-in ([scripts/check-replacements.sh](../../scripts/check-replacements.sh), every partition):
  an ELF file keeps every export that some program on the partition imports; an APEX keeps
  Google's name, version and file list, and its public files (those the partition symlinks to)
  keep every export.
- Google builds bionic and libz for Panther Lake (GFNI, AVX-VNNI); on the MSI's Zen 3 each such
  instruction traps into the kernel emulator. The same files from the pinned Android 17 emulator
  image (generic x86-64, same API) replace them, as Churro does. This removed about 99.7% of
  traps in QEMU (15.3 M → 44,644) and the softpipe boot animation ended at 66 s instead of 110 s.
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
- Google's `/system/build.prop` turns on mmd's zram writeback, so `mmd_setup` makes an 8 GiB file in
  `/data/per_boot/zram` on every boot and writes idle pages out to the USB, which runs at USB 2.0
  speed. [build-prop.patch](../../android/vendor/build-prop.patch) sets
  `mmd.zram.writeback.enabled=false`: zram swap stays in RAM and the 8 GiB stays free. Drop the line
  when /data is large and on fast storage. The laptop effect is not measured.

## Files
- [android/system/](../../android/system/), [android/system_ext/](../../android/system_ext/), [android/vendor/](../../android/vendor/) — every change to Google's partitions.
- [android/vendor_dlkm/](../../android/vendor_dlkm/), [tools/laptop_module_check.py](../../tools/laptop_module_check.py) — new signed modules, dependencies and laptop alias checks.
- [scripts/android-overlay.sh](../../scripts/android-overlay.sh) — applies one change directory; format in its header.
- [scripts/check-vendor-libs.sh](../../scripts/check-vendor-libs.sh) — library check for vendor programs we install.
- [scripts/check-replacements.sh](../../scripts/check-replacements.sh) — drop-in check for replaced Google files.
- [scripts/android-partition.sh](../../scripts/android-partition.sh), [tools/fs_metadata.py](../../tools/fs_metadata.py) — rebuild and full comparison.
- [scripts/android-disk.sh](../../scripts/android-disk.sh) — create the private disk once: data partition, FAT32 boot partition.
- [tests/test_android_disk.py](../../tests/test_android_disk.py) — its layout and refusals on a synthetic Google-shaped disk.
- [scripts/android-boot.sh](../../scripts/android-boot.sh), [tests/test_android_boot.py](../../tests/test_android_boot.py) — boot files into the FAT32 partition; its refusals, no-op and repair on a synthetic disk.
- [tools/android_sync.py](../../tools/android_sync.py), [tools/lp.py](../../tools/lp.py) — partition updates.
- [scripts/unpack.sh](../../scripts/unpack.sh) — Google image inventory (`out/google/inventory.txt`).
- [tests/test_unpack_hash.py](../../tests/test_unpack_hash.py) — mismatch and early-failure safety.

## Verify
`make test` (including recovery-image hash refusal in
[tests/test_unpack_hash.py](../../tests/test_unpack_hash.py), sync, lock and overlay tests in
[tests/test_overlay.py](../../tests/test_overlay.py);
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
- Non-`ro.` properties in `/vendor/build.prop` override `/system/build.prop`; init logs
  `Overriding previous property '…':'true' with new value 'false'`. The serial shell cannot read
  mmd's properties (`getprop` prints nothing), so check that kernel-log line and `df /data`.

## Actions
_None agreed._ The USB version of this disk is tracked in [laptop-hardware.md](laptop-hardware.md).

## Handoff log
- 2026-11-02 (this commit) — Turned off Google's mmd zram writeback (`build-prop.patch`): it made an
  8 GiB file in /data every boot. QEMU, previous vs new vendor: `loop45` of 16,777,216 sectors and
  `zram: setup backing device` vs neither; setup reached, enforcing. Laptop effect not measured.
- 2026-11-02 (this commit) — Pin and verify the recovery image's SHA-256 before unpacking; a
  mismatch is rejected before existing extracted files are removed. `make test`: 106 tests pass.
- 2026-11-02 (this commit) — Generic bionic/runtime APEX/libz from the emulator image, with a
  drop-in check. QEMU traps 15.3 M → 44,644; boot animation 110 s → 66 s; setup inspected.
  Hardware not yet tested: the runtime APEX's signing key differs from Google's (Churro boots it).
- 2026-11-02 (this commit) — Hardware candidate rebuilt with metadata/read-back checks; 100
  tests pass. 52,168,658,944 unaffected bytes preserved; idle no-op 15.94 s, all 23 timestamps
  unchanged. Disposable enforcing setup/input checked; physical USB update remains the owner's step.
- 2026-11-02 `uncommitted` — 87 tests pass; rebuilt system, system_ext and vendor_dlkm with kABI
  clean. Sync verified the OS writes and preserved userdata/metadata; repeat build wrote nothing.
  QEMU on a reflinked copy reaches setup with SELinux enforcing; physical transfer is pending.
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
