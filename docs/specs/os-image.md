# OS image and disk

**Status:** working — gbos-builder fresh image, verified rebuilds and guarded updates.
USB updater validation (2026-11-02): `make test` passes 129 tests, including regular-file combined
OS/boot update, cancellation, multi-extent preservation and a write-free repeat. Range derivation
on the real built image matches the old helper. Not verified: the new host mount/write workflow
on physical USB hardware; no physical disk was written for this change.
**Last verified:** 2026-11-04 — Full hardware recipes: 263 tests pass; 11 expanded declaration
surfaces and ordered patch bytes match `d901da2`. Image rebuild passes ABI/modules, metadata
and fit checks; all 38 tracked output hashes/sizes match before the build. The 23.8 s repeat
preserves timestamps/inodes too, with no partition/boot writes. Direct and USB-UEFI disposable
boots reach inspected setup under enforcing SELinux; a tap opens inspected Accessibility.
Both older disks and the deliverable remain untouched by boot tests. No physical writes.
[Evidence](../../out/full-hardware-recipes/).

Earlier, 2026-11-04 — Clean-break rename: 246 tests pass, including legacy label/
marker/directory refusal without writes. New `out/gbos-builder/disk.img` passes kernel ABI,
signed modules and filesystem metadata/fit checks. The 22.6 s repeat preserves 38 complete
output hashes/sizes/timestamps and writes no partitions or boot files. Direct/USB-UEFI QEMU
reach inspected setup with enforcing SELinux; an injected tap opens Accessibility.
Both older disks and all editable source trees remain preserved. No physical writes or retest.
[Evidence](../../out/gbos-builder-validation/).

Earlier, 2026-11-04 — Restored official Ruby recovery matches the unchanged image
SHA-256 pin; five offline fetch and four source-extraction tests pass. Image rebuild passes
all ABI/module/metadata/fit checks and preserves all 37 recorded output hashes/sizes, including
the full disk. A 21.4 s repeat preserves timestamps and writes no partitions/boot files.
No new QEMU or physical boot: runtime bytes match the existing baseline.
[Evidence](../../out/hardware-recipes/).

Earlier, 2026-11-03 — 92 focused tests pass; fresh expanded slot-A image builds with
`make android-image JOBS=12`;
all rebuilt filesystem metadata/import checks and all 4,501 Google exports pass. The exact six
A allocations and absence of logical B partitions/group are verified. Direct and USB/UEFI QEMU
reach inspected setup screens with enforcing SELinux; input opens accessibility in the direct
test and a low-battery setup warning in UEFI (setup not completed). Two repeat builds preserve
all 74 recorded published files and full disk hashes/timestamps,
with no partition writes. Old local disk and physical USB untouched. Lenovo GPU and MSI
hardware regression remain untested. [Evidence](../../out/intel-bringup/fresh/).
Earlier the same day: Copy-only super migration: 43 focused migration/image/USB tests
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
Verified: native hardware recipes now supply device assets, driver libraries/firmware,
whole-file removals and explicitly ordered Android patches through the existing overlay.
Shared security/logging/native-bridge/storage changes stay common. Source-derived combined
module metadata remains intact in `laptop-modules`; arbitrary driver removal is not automatic.
The owner approved tests/build; exact input/output preservation and disposable QEMU checks
pass above. The combined image remains `out/gbos-builder/disk.img`, ready for owner testing.

Verified: clean-break gbos-builder identity uses a separate `out/gbos-builder/disk.img`,
FAT label `GBOS-BOOT`, boot directory `gbos-builder/` and new format markers.
Existing Dali media are deliberately rejected before updater writes; the owner must explicitly
flash a fresh image to use this generation. No compatibility aliases or data migration.
Both existing private disk images remain untouched. Tests/build/QEMU validation pass above.
Mesa/minigbm source prerequisites are order-only: their bytes already select content-keyed
trees, so newer timestamps must not attempt to replace editable caches. Regression-tested.
Not verified: renamed media on physical hardware; a fresh flash remains an explicit owner action.

Recovery-source restoration verified: the old reference file no longer matched the pinned
baseline, so the build refused it before extraction. A separate official Ruby `16658739`
download now matches the unchanged image SHA-256 and is the default hash-named source cache.
The downloader verifies the extracted ZIP member before publishing it; raw downloads retain
their existing checks. The altered reference file remains untouched. Read-only comparison
localizes its changes to the metadata partition; the cause of those changes is unknown.

The owner approved a fresh image rather than migration, with additional growth space.
[super-layout.json](../../android/super-layout.json) declares system 2 GiB, vendor 1 GiB,
product 3 GiB, system_ext 1 GiB and both module partitions 64 MiB. Logical B partitions and their
unused group are removed; small physical B entries and the 12 GiB outer super allocation remain.
[android_fresh.py](../../tools/android_fresh.py) builds the super through upstream lpmake,
creates a new disk from recovery, checks super read-back, installs vbmeta/boot files, then
publishes privately and atomically. The working path is now `out/gbos-builder/disk.img`;
the old `out/android/disk.img` is never replaced. New userdata starts empty, not copied from the
old disk. Later builds update only OS/boot files and enforce the declared logical allocations.
To deploy, the owner must flash the fresh image once: this erases the USB's existing data.
The unchanged USB updater rejects an old layout and works only after a matching full flash.
`make install-usb JOBS=12` provides the owner-run full flash: reuse USB-only selection and
identity/in-use checks, require exact `ERASE <serial>`, copy the entire image and verify SHA-256
read-back. It does not grow partitions; larger USBs keep the backup GPT at the image boundary,
as with a raw flash. Owner's larger USB boots, but the subsequent updater rejected this
placement with `MyLBA mismatch`. The shared installer/updater check now compares all GPT
metadata bytes (PMBR, both headers and arrays) with the verified source for this exact case;
other layouts still require normal `sfdisk --verify`. No GPT relocation or disk writes by agent.
All 32 installer/updater tests pass in the builder, including an actual raw flash to a larger
regular file, unchanged GPT/timestamps, damaged metadata refusal and relocated/equal-size GPTs.
Verification also rejects stderr diagnostics when older `sfdisk` exits zero despite errors.
[Evidence](../../out/intel-primary-alpha/usb-gpt-tests.log). Owner's physical update retest remains.

Earlier disposable Intel-layout experiment (2026-11-03): upstream `lpmake` generates a separate
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
That earlier experiment did not alter the working disk, enable normal Intel image builds or
migrate a USB; the fresh expanded pipeline above supersedes it.

Verified: `system_a`, `vendor_a`, `system_ext_a`, `vendor_dlkm_a` rebuilt as EROFS with every file's bytes,
mode, owner, xattrs and SELinux label checked; development `vbmeta_a` from `avbtool`; disk
`out/android/disk.img` with a 32 GiB sparse userdata and a 576 MiB FAT32 EFI-SYSTEM (`DALI-BOOT`, pre-rename,
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
- Tests follow ownership: device/driver checks and local fixtures live in recipe `tests/`
  directories; generic tool/safety and cross-recipe integration tests remain central.
  `make test` runs all recipes, including unselected ones, through
  [run_tests.py](../../tools/run_tests.py); focused runs accept files or directories.
- Clean-break gbos-builder rename: new boot/Android identities, no legacy aliases or migration.
  Use a separate new disk path; preserve older images, editable source caches and history.
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
  kept; output must not exceed its declared allocation in [super-layout.json](../../android/super-layout.json).
  LZ4HC level 9 with 256 KiB clusters:
  2–3x faster to build than level 12 and about 0.2% larger (system 1053 MB of 1134 MB).
  Exception: vendor_dlkm uses Zstd level 9, now 19,652,608 B within its 64 MiB allocation.
  Zstd retains every Google module without unnecessary image growth.
- AVB is disabled through a new vbmeta (`--algorithm NONE --flags 3`); SELinux stays enforcing.
- The disk is a reflink copy of the recovery image with userdata moved to the end and grown;
  slot A marked bootable/successful. It holds Android's data, so it is **never recreated automatically**.
- Fresh expanded layout instead of migration (owner-approved): keep growth space in A-only
  logical partitions; retain physical B boot-control entries. Existing disks need a new image
  path/full owner-run flash, never an in-place layout overwrite or relaxed updater checks.
- EFI-SYSTEM absorbs the blank `KERN-A` beside it and is formatted FAT32 for the laptop's boot
  files; it keeps its PARTUUID, which the initrd uses to find the disk. The script refuses unless
  both partitions are adjacent and all zeros, so a newer Google image is never formatted over.
  QEMU's direct-kernel boot ignores it.
- The boot files go into that partition with mtools, never a mount or loop device
  ([scripts/android-boot.sh](../../scripts/android-boot.sh)), and only when the partition is
  the FAT32 labelled `GBOS-BOOT`. `EFI/` and `gbos-builder/` are replaced as a whole and read back; if
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
- [tools/install_usb.py](../../tools/install_usb.py) — owner-run destructive fresh flash;
  [tests/test_install_usb.py](../../tests/test_install_usb.py) — regular-file safety regressions.
- [android/super-layout.json](../../android/super-layout.json) — shared A-only logical allocations.
- [tools/android_fresh.py](../../tools/android_fresh.py) — guarded first creation of the expanded disk;
  [tests/test_android_fresh.py](../../tests/test_android_fresh.py).
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
`make android-image JOBS=12` creates the fresh expanded disk once, then updates it without
recreating data. The first USB flash is the owner's operation and erases the selected USB;
later `make update-usb JOBS=12` preserves data only on a matching layout.

Earlier copy-only experiment (not the production layout):
For a disposable migration of the installed local image (never a device):
```sh
make lp-tools JOBS=12
scripts/builder.sh python3 tools/super_migrate_copy.py \
  out/lp-tools/lpmake out/android/disk.img out/migration/migrated.img
```
Keep this private copy under ignored `out/`. **Do not flash it onto an existing USB:** it
contains the local disk's userdata, metadata and boot identity, not the USB's current data.
This 32 MiB copy-only tool is not the new expanded production layout; no working/USB migration
is planned after the owner chose a fresh flash.

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
- [ ] Owner flashes the expanded image and tests Lenovo/MSI — done when fresh setup, actual GPU
  binding/renderer and MSI regression evidence are confirmed. No physical disk writes by the agent.
- [ ] First physical use of `make update-usb JOBS=12` — done when the owner selects the existing
  USB, verifies OS and boot updates succeed, confirms data remains intact and sees a no-write
  repeat. The USB version of this disk is tracked in [laptop-hardware.md](laptop-hardware.md).

## Handoff log
- 2026-11-04 (this commit) — Relocated hardware checks beside recipes; 282 tests pass,
  preserving all 273 original methods with split checks and discovery regressions added.
  Focused device/driver run passes; no image/runtime changes or image rebuild needed.
- 2026-11-04 uncommitted — Combined image rebuilt/verified for MSI and Lenovo. 263 tests,
  38-output byte equality and no-write repeat pass; disposable direct/UEFI boots inspected.
  No physical writes or source-tree replacement; physical regression remains with the owner.
- 2026-11-04 uncommitted — Added ordered recipe patch manifests and recipe-local install sources;
  preserved overlay metadata/path checks. No new tests, build, boot or commit yet.
- 2026-11-04 (this commit) — Clean-break identity/new image path; old disks/trees preserved.
  246 tests, ABI/metadata/fit, enforcing direct/UEFI/input, Berberis and no-write repeat pass.
  Fix timestamp-only Mesa/minigbm re-extraction; physical media/hardware remain untested.
- 2026-11-04 (this commit) — Restored pinned Ruby source into a separate cache after the
  reference file changed only in metadata. Five fetch/four source tests and rebuilt output
  equality/no-write repeat pass; old source preserved, no new QEMU or physical writes.
- 2026-11-03 (this commit) — Larger raw-flashed USB exposed GPT placement rejection. Shared
  read-only comparison accepts only exact verified-source GPT bytes; sfdisk diagnostics fail
  even on zero exit. 32 regular-file tests pass; owner update retest pending, no agent disk writes.
- 2026-11-03 (this commit) — Added separate owner-run `install-usb`: explicit serial erase
  confirmation, USB identity/in-use/capacity guards and full-image read-back. Regular-file
  installer/shared updater tests pass; physical flash untested and never run by the agent.
- 2026-11-03 (this commit) — Fresh enlarged A-only image, shared allocation/fit guards and new
  disk path; logical B removed, physical B retained. Build/kABI/metadata, direct/UEFI QEMU and
  two no-write repeats pass. Old disk/USB untouched; owner full flash/hardware retests pending.
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
