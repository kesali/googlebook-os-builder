# OS image and disk

**Status:** working — declared change lists and patches, verified rebuilds, data-preserving updates.
USB updater validation (2026-11-02): `make test` passes 129 tests, including regular-file combined
OS/boot update, cancellation, multi-extent preservation and a write-free repeat. Range derivation
on the real built image matches the old helper. Not verified: the new host mount/write workflow
on physical USB hardware; no physical disk was written for this change.
**Last verified:** 2026-11-03 — Copy-only super migration: 43 focused migration/image/USB tests
pass. All A payloads and every byte outside super are preserved on a disposable disk copy;
full source/candidate hashes and timestamps stay unchanged on repeat refusal/no-op checks.
Enforcing UEFI/QEMU reaches the inspected setup screen and responds to an injected tap.
The working disk and physical USB remain unchanged; normal Intel builds/deployment are blocked.
[Evidence](../../out/intel-bringup/migration/).
Earlier the same day: 28 focused image/USB tests pass in the builder. Cached
`make android-image JOBS=12` runs took 18 and 19 seconds; both verified the GPT and wrote no
partitions or boot files. All 76 recorded output files kept their metadata and non-disk hashes;
GPT, liblp, the metadata partition and sampled userdata matched. The entire disk was not hashed.
No QEMU boot or physical USB update was performed for this change.
Earlier, 2026-11-02: native-bridge diagnostics rebuilt only system/system_ext;
3,642/236 entries passed metadata checks. The repeat preserved image/bundle timestamps and
wrote no partitions. 53 focused tests and two enforcing UEFI/QEMU runs pass
([build](../../out/arm-translation-diagnostic/build.log),
[runtime](../../out/arm-translation-diagnostic/verification-final.log)).
The same small ARM64 executable traps in normal Houdini but runs in optional Berberis;
the default stays Houdini. The owner subsequently updated the USB and reports the previously
failing game, another native app and Hearthstone work with Berberis; no new laptop logs retrieved.
Earlier, the source-level YV12 fixes rebuilt only vendor; all 1,620
entries passed metadata checks. Repeat build wrote no partitions; enforcing QEMU reached the
inspected setup screen ([build](../../out/video-yv12-build.log),
[QEMU](../../out/video-yv12-qemu.log)); 131 tests pass. The owner subsequently deployed these
source fixes and confirms video playback is fixed; see [graphics](graphics.md).
Earlier, on the physical stick, `update-os.sh` wrote only `vendor_a` and a
second run found all five OS ranges unchanged on the enlarged layout; `grow-data.sh --erase-data`
grew `userdata` from 32 GiB to 215.1 GiB (451,151,872 sectors), read back a blank first MiB and left
the rest of the table identical to the image
([update-os.log](../../out/usb-flash-android/update-os.log),
[grow-data.log](../../out/usb-flash-android/grow-data.log)). The owner subsequently booted it. Before that,
`make android-image JOBS=12` rebuilt only vendor (24 s) with zram writeback off. A QEMU boot of a
copy with userdata grown to 64 GiB and its first MiB zeroed (what
`grow-data.sh` leaves) formatted `/data` at 61 GiB, reached setup with SELinux enforcing and had no
8 GiB writeback device in the kernel log, where the previous vendor image had one
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
Disposable Intel-layout experiment (2026-11-03): upstream `lpmake` generates a separate
12 GiB super image with `vendor_dlkm_a` enlarged to 32 MiB and every logical B entry retained
but empty. The Zstd-9 i915 candidate is 19,636,224 B; all 513 entries pass metadata checks.
Geometry, group limits, six primary/backup metadata copies and every supplied A payload/padding
are verified by [super_candidate.py](../../tools/super_candidate.py). Six focused safety tests
pass; a second generated super matches every byte, and an unchanged `make lp-tools` preserves
the tool/build metadata timestamps. The working disk/USB and their layouts remain unchanged.
This first super-only candidate was not boot-tested and is not accepted by the existing updater.
Build the host tool with `make lp-tools JOBS=12`; the candidate builder's `--help` documents
its explicit inputs. [Evidence](../../out/intel-bringup/super-32m.log).
The subsequent Iris candidate also passes enforcing direct-kernel and USB/UEFI QEMU with
inspected setup/input screens; see [graphics](graphics.md). This does not establish Intel
hardware support or permit deploying the enlarged layout through the existing USB updater.

The copy-only [migration tool](../../tools/super_migrate_copy.py) now extracts the installed
A partitions and uses the verified upstream builder to create the enlarged layout on a new
regular-file disk copy. It requires successful slot A, inactive B and identical metadata copies,
holds the source disk lock, verifies read-back and every byte outside super, then publishes
atomically with private permissions. Existing destinations, devices and `disk.img` outputs are
refused. A migrated source is a no-write no-op. Nine migration tests plus 34 related tests pass;
the migrated copy also passes enforcing USB/UEFI QEMU with inspected setup/input screens.
This does not alter the working disk, enable normal Intel image builds, or migrate a USB.

Verified: `system_a`, `vendor_a`, `system_ext_a`, `vendor_dlkm_a` rebuilt as EROFS with every file's bytes,
mode, owner, xattrs and SELinux label checked; development `vbmeta_a` from `avbtool`; disk
`out/android/disk.img` with a 32 GiB sparse userdata and a 576 MiB FAT32 EFI-SYSTEM (`DALI-BOOT`,
Google's PARTUUID) holding the laptop's boot files; updates copy only changed partitions
with read-back hashes; unchanged builds write no disk partitions; updates refuse to run while the VM holds the disk lock.
OVMF reads the FAT32 ESP and Android finds its partitions over USB (`make android-uefi-check`,
2026-11-01; [laptop-hardware.md](laptop-hardware.md)). Its disposable boots left the source disk
byte-identical. The owner later completed physical setup with Wi-Fi and input on an earlier image.
The stick holds that image and a 215 GiB userdata partition and has since been booted
([laptop-hardware.md](laptop-hardware.md)); the owner confirms the codec/YV12 update fixes video.
The owner deployed the optional native-bridge diagnostics and confirmed previously failing apps
work with Berberis ([boot](boot.md)).
The system/system_ext logging changes and removal of vendor's precompiled policy are built
and verified through the QEMU smoke test ([boot.md](boot.md)). The image updater changed only
the OS partitions named above; Android userdata, metadata and layout were preserved. That
QEMU test used a reflinked copy.

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
- `make update-usb` is the supported physical USB update workflow: build in the container, then
  run the host updater with sudo. List USB disks, select explicitly, then confirm with `y`/`yes`
  at a default-no prompt showing the device path, model and serial.
  Require matching GPT/liblp and the Android boot marker, preserve larger userdata, and update
  OS ranges plus boot files with read-back. Private boot mounts are read-only until confirmation;
  payloads precede the menu. Never format, repartition, auto-select or offer internal disks.
- `/data` cannot grow without being erased: its ext4 has no `resize_inode` and ends on a
  group-descriptor boundary (no online `resize2fs`), and an offline resize needs the metadata
  encryption key, which we never extract. Enlarging the partition alone changes nothing. The
  owner-run, ignored `out/usb-flash-android/grow-data.sh` enlarges `userdata` and, if it holds data,
  blanks its first MiB so fs_mgr formats `/data` at the new size. Apart from a full flash it is the
  only helper that writes userdata, and it needs `--erase-data` plus a typed `ERASE` whenever data
  would be lost. It never shrinks; the tracked USB updater accepts a larger userdata while requiring
  the rest of the layout to match.
- Dependencies are per partition: Mesa, minigbm, firmware, emulator and crossystem rebuild vendor
  only; system_ext changes rebuild system_ext; the signed module manifest rebuilds vendor_dlkm.
- Google's `/system/build.prop` turns on mmd's zram writeback, so `mmd_setup` makes an 8 GiB file in
  `/data/per_boot/zram` on every boot and writes idle pages out to the USB, which runs at USB 2.0
  speed. [build-prop.patch](../../android/vendor/build-prop.patch) sets
  `mmd.zram.writeback.enabled=false`: zram swap stays in RAM and the 8 GiB stays free. Drop the line
  when /data is large and on fast storage. The laptop effect is not measured.

## Files
- [tools/super_migrate_copy.py](../../tools/super_migrate_copy.py) — verified, copy-only layout
  migration; [tests/test_super_migrate_copy.py](../../tests/test_super_migrate_copy.py).
- [android/system/](../../android/system/), [android/system_ext/](../../android/system_ext/), [android/vendor/](../../android/vendor/) — every change to Google's partitions.
- [android/vendor_dlkm/](../../android/vendor_dlkm/), [tools/laptop_module_check.py](../../tools/laptop_module_check.py) — new signed modules, dependencies and laptop alias checks.
- [scripts/android-overlay.sh](../../scripts/android-overlay.sh) — applies one change directory; format in its header.
- [scripts/check-vendor-libs.sh](../../scripts/check-vendor-libs.sh) — library check for vendor programs we install.
- [scripts/check-replacements.sh](../../scripts/check-replacements.sh) — drop-in check for replaced Google files.
- [scripts/android-partition.sh](../../scripts/android-partition.sh), [tools/fs_metadata.py](../../tools/fs_metadata.py) — rebuild and full comparison.
- [scripts/android-disk.sh](../../scripts/android-disk.sh) — create the private disk once: data partition, FAT32 boot partition.
- [tests/test_android_disk.py](../../tests/test_android_disk.py) — its layout and refusals on a synthetic Google-shaped disk.
- [scripts/android-boot.sh](../../scripts/android-boot.sh), [tests/test_android_boot.py](../../tests/test_android_boot.py) — boot files into the FAT32 partition; its refusals, no-op and repair on a synthetic disk.
- [tools/android_sync.py](../../tools/android_sync.py), [tools/android_layout.py](../../tools/android_layout.py)
  and [tools/lp.py](../../tools/lp.py) — partition updates and shared layout checks.
- [tools/update_usb.py](../../tools/update_usb.py), [tests/test_update_usb.py](../../tests/test_update_usb.py)
  — host USB selection, layout checks, incremental OS and menu-last boot updates.
- [scripts/unpack.sh](../../scripts/unpack.sh) — Google image inventory (`out/google/inventory.txt`).
- [tests/test_unpack_hash.py](../../tests/test_unpack_hash.py) — mismatch and early-failure safety.

## Verify
For a disposable migration of the installed local image (never a device):
```sh
make lp-tools JOBS=12
scripts/builder.sh python3 tools/super_migrate_copy.py \
  out/lp-tools/lpmake out/android/disk.img out/migration/migrated.img
```
Keep this private copy under ignored `out/`. **Do not flash it onto an existing USB:** it
contains the local disk's userdata, metadata and boot identity, not the USB's current data.
Working-disk migration and an interruption-safe owner-run USB operation need separate approval;
do not run `make android-image` or `make update-usb` with the uncommitted Intel modules yet.

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
- [android_sync.py](../../tools/android_sync.py) and the USB updater share checks for extents
  inside liblp metadata, outside `super`, or overlapping another parsed partition. Both verify
  the GPT before writing. General liblp parser structural hardening is not part of this change.
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
- `grow-data.sh` ran on the physical stick: with no `ERASE` on stdin it printed its plan and stopped
  without writing, then the real run passed its own checks. Its logic is also tested on regular-file
  copies shaped like the stick ([script-test.sh](../../out/data-growth-validation/script-test.sh),
  68 checks, about 10 s). After a wipe, factory-reset protection may ask for the previous Google
  account (untested).

## Actions
- [ ] Agree the working-disk migration/build allocation and owner-run USB procedure — done when
  separately approved and verified to preserve each target's own data with interruption recovery.
- [ ] First physical use of `make update-usb JOBS=12` — done when the owner selects the existing
  USB, verifies OS and boot updates succeed, confirms data remains intact and sees a no-write
  repeat. The USB version of this disk is tracked in [laptop-hardware.md](laptop-hardware.md).

## Handoff log
- 2026-11-03 (this commit) — Copy-only layout migration: 43 tests, all-A/read-back/outside-super
  preservation and full-hash/timestamp no-op checks pass. Enforcing UEFI setup/input inspected.
  Working disk/USB unchanged; normal Intel build allocation and deployment remain unimplemented.
- 2026-11-03 (this commit) — Pinned upstream lpmake and guarded disposable 32 MiB vendor_dlkm
  experiment; six tests, 513-entry image metadata/fit, liblp/payload checks and byte-identical
  repeat pass. Working disk/USB untouched; candidate boot and layout migration unimplemented.
- 2026-11-03 (this commit) — Shared local/USB extent and GPT checks without changing the
  extractor; 28 focused tests, cached image build and no-write repeat pass. Physical USB untested.
- 2026-11-02 (this commit) — Compared local and USB extent guards; the current private disk
  passes the stronger USB check, but local-sync metadata/overlap validation remains a gap.
- 2026-11-02 (this commit) — Replaced serial retyping with default-no `y`/`yes` confirmation
  after selection and the update summary; device identity/layout/read-back safeguards unchanged.
  All 15 focused updater tests pass using regular-file fixtures; no physical disk writes.
- 2026-11-02 (this commit) — Native-bridge selection and crash capture changed only system and
  system_ext; metadata, 53 focused tests, no-write repeat and two enforcing UEFI runs pass.
  Owner deployed and confirms the failing game, another native app and Hearthstone work in Berberis.
- 2026-11-02 (this commit) — Rebuilt vendor with RADV external-format and allocator planar-pitch
  source fixes; 1,620 metadata entries and allocator ABI pass. 131 tests and enforcing QEMU pass;
  repeat writes nothing. USB unchanged; owner retest pending.
- 2026-11-02 (this commit) — Promoted USB updates into `make update-usb`: select/confirm by serial,
  derive OS extents, preserve data/layout, reuse menu-last boot installation. 129 tests pass and
  real-image ranges match; physical USB use remains untested. No disk written.
- 2026-11-02 (this commit) — Added the software-codec vendor seccomp extension for Mesa's
  affinity query. Vendor-only rebuild and unchanged repeat pass; enforcing QEMU setup and software
  AVC encoding pass. The physical stick is unchanged; playback retest remains.
- 2026-11-02 (this commit) — At the owner's request (test data) wrote the stick: `deploy-android`,
  `update-os.sh` (`vendor_a` only, 369 MiB) and `grow-data.sh --erase-data` (userdata 32 → 215.1 GiB,
  blanked). A second `update-os.sh` wrote nothing; the boot-file deploy re-ran as a no-op. Not booted.
- 2026-11-02 (this commit) — Added the owner-run `grow-data.sh` (ignored, under out/) to enlarge /data;
  it erases /data because no resize is possible. `update-os.sh` accepts a larger userdata. Tested on
  file copies (68 checks) and a 64 GiB QEMU boot; the physical stick and its guards are untested.
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
