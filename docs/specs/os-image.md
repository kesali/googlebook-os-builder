# OS image and disk

**Status:** partial — compact GPT/direct FAT32 image and direct QEMU pass; physical install pending.
USB updater validation (2026-11-02): `make test` passes 129 tests, including regular-file combined
OS/boot update, cancellation, multi-extent preservation and a write-free repeat. Range derivation
on the real built image matches the old helper. Not verified: the new host mount/write workflow
on physical USB hardware; no physical disk was written for this change.
**Last verified:** 2026-11-05 — Combined image builds in 4m1s; all kABI/module/filesystem/fit
checks pass. FAT mount policy fix rebuilds system only in 40 s. A 24.3 s repeat preserves all
67 tracked published sizes/timestamps and writes no partitions/boot files. Direct normal and
diagnostic QEMU setup/focus inspected under enforcing SELinux; normal boots preserve the
entire saved 256 MiB FAT partition. Older disks and physical media untouched.
[Evidence](../../out/common-hardware-validation/).

Earlier, 2026-11-05 — 107 focused tests pass through the builder:
disk/fresh/install/update, bootlog, laptop-log retrieval and overlay tests.
Real regular-file fixtures verify 256 MiB FAT32 creation, boot-record guards/retention,
read-only FAT32 extraction with unchanged source hash/timestamp and updater preservation.
No image build, enforcing mount/boot check or physical write.
[Test log](../../out/fat32-logging-tests.log).
The owner approved committing this focused-tested milestone and deferring image, emulator and
physical-hardware validation until after further changes.

Earlier, 2026-11-05 — 67 focused tests pass through the builder:
`test_android_disk`, `test_android_fresh`, `test_install_usb`, `test_update_usb`, `test_overlay`.
Regular-file fixtures verify compact GPT/FAT32 creation, backup GPT relocation, userdata growth,
metadata/signature reset, other-payload preservation and refusal paths. No image build, QEMU,
physical write or commit. [Test log](../../out/compact-layout-tests.log).

Earlier, 2026-11-04 — Full hardware recipes: 263 tests pass; 11 expanded declaration
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
`make android-image`;
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
`make android-image` runs took 18 and 19 seconds; both verified the GPT and wrote no
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
`make android-image` rebuilt only vendor (24 s) with zram writeback off. A QEMU boot of a
copy with userdata grown to 64 GiB and its first MiB zeroed (what
`grow-data.sh` leaves) formatted `/data` at 61 GiB, reached setup with SELinux enforcing and had no
8 GiB writeback device in the kernel log, where the previous vendor image had one
([evidence](../../out/data-growth-validation/)); `make test` passes 113 tests. Earlier the same day:
`make android-image` (54 s) rebuilt system, vendor, system_ext and vendor_dlkm; every
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
USB prompts: install/update now select the disk before requesting sudo, matching
log retrieval. Privileged re-entry rechecks device identity and usage; existing write
confirmations and descriptor checks remain. The three USB test files pass all 59 tests through
the builder; evidence: [tests.txt](../../out/usb-prompt-order/tests.txt).

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

Verified build/direct QEMU: the owner-approved compact replacement uses
`out/gbos-builder/compact/disk.img`, leaving both older working disks untouched.
[android_disk.py](../../tools/android_disk.py) now creates 14 aligned GPT entries: EFI-SYSTEM,
super, boot_a, init_boot_a, vendor_boot_a, vbmeta_a, vbmeta_b, misc, metadata,
desktop_security_persist, desktop_security_storage, frp_persist, gbos_logs and trailing userdata.
Retained UUIDs/types and small payloads survive; boot storage, metadata and userdata start fresh.
`vbmeta_b` is a 4 MiB boot-HAL compatibility entry, not a second OS slot.
The owner approved a 256 MiB FAT32 `GBOS-LOGS` partition for direct diagnostic logging,
not periodic export. It has a stable UUID derived from the source disk UUID and a Microsoft
basic-data partition type. Normal boots leave it unmounted; ordinary updates preserve it.
Creation/retrieval tests and enforcing QEMU mount/runtime pass after the scoped init
filesystem relabel fix; normal boots leave every FAT byte unchanged.
The [build guide](../build-guide.md#compact-partition-layout) lists the physical partition
order, sizes and purposes, logical allocations, and fresh-install/update behavior.

[super-layout.json](../../android/super-layout.json) now allocates system 3 GiB, vendor 1.5 GiB,
product 4 GiB, system_ext 1.5 GiB and each module partition 256 MiB: 10.5 GiB within 12 GiB super.
A read-only inspection found the original A group limit is 12,880,707,584 bytes, enough without
changing the upstream group bound. Build/fit and direct QEMU boot pass; fresh physical
installation and compact-image USB-UEFI checks remain unverified.
Fresh USB installation verifies the full copy, resets metadata and the first MiB of userdata,
relocates backup GPT and expands userdata before Android's first format. It deliberately discards
copied QEMU accounts/encryption state, not securely erasing every old data sector.
Normal updates still require matching GPT/liblp except larger userdata; old-layout media need
an explicit destructive installation. The earlier 13-entry baseline passed 67 focused tests;
the additional FAT32 changes now pass the 107-test focused run. No compact image or boot yet.

Earlier expanded layout: the owner approved a fresh image rather than migration, with growth space.
[super-layout.json](../../android/super-layout.json) declares system 2 GiB, vendor 1 GiB,
product 3 GiB, system_ext 1 GiB and both module partitions 64 MiB. Logical B partitions and their
unused group are removed; small physical B entries and the 12 GiB outer super allocation remain.
[android_fresh.py](../../tools/android_fresh.py) builds the super through upstream lpmake,
creates a new disk from recovery, checks super read-back, installs vbmeta/boot files, then
publishes privately and atomically. Its working path was `out/gbos-builder/disk.img`;
the old `out/android/disk.img` is never replaced. New userdata starts empty, not copied from the
old disk. Later builds update only OS/boot files and enforce the declared logical allocations.
To deploy, the owner must flash the fresh image once: this erases the USB's existing data.
The unchanged USB updater rejects an old layout and works only after a matching full flash.
`make install-usb` provides the owner-run full flash: reuse USB-only selection and
identity/in-use checks, require default-no `y`/`yes` confirmation, copy the entire image and verify SHA-256
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
Build the host tool with `make lp-tools`; the candidate builder's `--help` documents
its explicit inputs. [Evidence](../../out/intel-bringup/super-32m.log).
The subsequent Iris candidate also passes enforcing direct-kernel and USB/UEFI QEMU with
inspected setup/input screens; see [graphics](graphics.md). This does not establish Intel
hardware support or permit deploying the enlarged layout through the existing USB updater.

A copy-only migration tool later built the enlarged layout from the installed disk and passed
enforcing USB/UEFI QEMU. The fresh expanded pipeline above superseded it, and it was removed
on 2026-11-05 (recoverable from Git history); no working disk or USB was ever migrated.

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
- Config-only hardware enablement stays grouped in the shared kernel config; dedicated driver
  recipes hold support needing additional assets such as patches, firmware, packaging or tests.
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
- Keep bionic, linker and the runtime APEX as one generic replacement set; do not add CPU-based
  runtime selection unless measurements show a meaningful benefit and selection is verified to
  happen before affected processes start. A standalone library such as libz can be evaluated
  separately if there's evidence of a benefit.
- Rebuild without root: `fsck.erofs` extraction and `mkfs.erofs` under fakeroot; original UUID
  kept; output must not exceed its declared allocation in [super-layout.json](../../android/super-layout.json).
  LZ4HC level 9 with 256 KiB clusters:
  2–3x faster to build than level 12 and about 0.2% larger (system 1053 MB of 1134 MB).
  Exception: vendor_dlkm uses Zstd level 9, now 19,652,608 B within its 64 MiB allocation.
  Zstd retains every Google module without unnecessary image growth.
- AVB is disabled through a new vbmeta (`--algorithm NONE --flags 3`); SELinux stays enforcing.
- The disk is a compact GPT assembled from recovery, keeping retained UUIDs/types and payloads;
  slot A is marked bootable/successful. It holds Android's data, so it is **never recreated automatically**.
- Fresh compact layout instead of migration (owner-approved): keep `_a` names and growth space
  inside 12 GiB super; remove physical B/C entries except the tiny `vbmeta_b` HAL compatibility
  entry. Keep small security/persistent partitions until their removal is proven safe.
  Existing disks need a new image
  path/full owner-run flash, never an in-place layout overwrite or relaxed updater checks.
- Direct opt-in diagnostics on 256 MiB FAT32 `GBOS-LOGS`, before userdata. Mount only for
  diagnostic boots; keep bounded current/previous captures, no metadata fallback or auto-format.
  Logs are unencrypted. Failed mounts must not start persistent collectors or block Android.
- The new 576 MiB EFI-SYSTEM is formatted FAT32 for the laptop's boot files; it keeps its
  PARTUUID, which the initrd uses to find the disk. No recovery partition is overwritten:
  the generator builds a separate regular file. QEMU's direct-kernel boot ignores its contents.
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
  supported fresh installer therefore resets metadata/encryption state and the userdata
  signature after copy verification, then expands userdata and verifies GPT before first boot.
  This is destructive fresh installation, never a live resize or an ordinary update.
  The updater accepts larger userdata while requiring the rest of the layout to match.
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
- [android/system/](../../android/system/), [android/system_ext/](../../android/system_ext/), [android/vendor/](../../android/vendor/) — every change to Google's partitions.
- [android/vendor_dlkm/](../../android/vendor_dlkm/), [tools/laptop_module_check.py](../../tools/laptop_module_check.py) — new signed modules, dependencies and laptop alias checks.
- [scripts/android-overlay.sh](../../scripts/android-overlay.sh) — applies one change directory; format in its header.
- [scripts/check-vendor-libs.sh](../../scripts/check-vendor-libs.sh) — library check for vendor programs we install.
- [scripts/check-replacements.sh](../../scripts/check-replacements.sh) — drop-in check for replaced Google files.
- [scripts/android-partition.sh](../../scripts/android-partition.sh), [tools/fs_metadata.py](../../tools/fs_metadata.py) — rebuild and full comparison.
- [tools/android_disk.py](../../tools/android_disk.py) — create the compact private GPT once.
- [tests/test_android_disk.py](../../tests/test_android_disk.py) — its layout and refusals on a synthetic Google-shaped disk.
- [scripts/android-boot.sh](../../scripts/android-boot.sh), [tests/test_android_boot.py](../../tests/test_android_boot.py) — boot files into the FAT32 partition; its refusals, no-op and repair on a synthetic disk.
- [tools/android_sync.py](../../tools/android_sync.py), [tools/android_layout.py](../../tools/android_layout.py)
  and [tools/lp.py](../../tools/lp.py) — partition updates and shared layout checks.
- [tools/update_usb.py](../../tools/update_usb.py), [tests/test_update_usb.py](../../tests/test_update_usb.py)
  — host USB selection, layout checks, incremental OS and menu-last boot updates.
- [scripts/unpack.sh](../../scripts/unpack.sh) — Google image inventory (`out/google/inventory.txt`).
- [tests/test_unpack_hash.py](../../tests/test_unpack_hash.py) — mismatch and early-failure safety.

## Verify
`make android-image` creates the fresh expanded disk once, then updates it without
recreating data. The first USB flash is the owner's operation and erases the selected USB;
later `make update-usb` preserves data only on a matching layout.

`make test` (including recovery-image hash refusal in
[tests/test_unpack_hash.py](../../tests/test_unpack_hash.py), sync, lock and overlay tests in
[tests/test_overlay.py](../../tests/test_overlay.py);
disk layout in [tests/test_android_disk.py](../../tests/test_android_disk.py); boot files in
[tests/test_android_boot.py](../../tests/test_android_boot.py)),
then `make android-image`. A second run
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
- [ ] After owner approval for image validation, check compact image GPT/liblp,
  graphical/input boot and no-write repeat; done when evidence is recorded without altering
  either older image or writing physical media.
- [ ] Owner flashes the expanded image and tests Lenovo/MSI — done when fresh setup, actual GPU
  binding/renderer and MSI regression evidence are confirmed. No physical disk writes by the agent.
- [ ] First physical use of `make update-usb` — done when the owner selects the existing
  USB, verifies OS and boot updates succeed, confirms data remains intact and sees a no-write
  repeat. The USB version of this disk is tracked in [laptop-hardware.md](laptop-hardware.md).

## Handoff log
- 2026-11-05 (this commit) — Fresh installation uses default-no `[y/N]`, matching updates,
  instead of serial retyping. Erase warnings and serial identity checks retained.
  All 45 installer/updater tests pass; no physical USB access.
- 2026-11-05 (this commit) — Unified USB prompts as disk selection then sudo; privileged
  re-entry rechecks identity/usage without a second selection. Write confirmations retained.
  All 59 focused USB tests pass; no physical USB access or interactive sudo test.
- 2026-11-05 uncommitted — Compact image builds with common drivers; all metadata/fit and
  67-file no-write repeat pass. Enforcing direct QEMU verifies FAT logging and normal-boot
  preservation; setup/focus inspected. No physical writes; compact USB-UEFI not tested.
- 2026-11-05 uncommitted — Owner approved direct FAT32 logging instead of export. Added
  256 MiB `gbos_logs` before userdata, gated mount/policy and read-only mtools retrieval.
  107 focused tests pass; image/enforcing runtime validation pending. Old disks untouched.
- 2026-11-05 uncommitted — Documented the compact physical/logical partition tables and
  growth/update contract in the build guide. Separate FAT32 log storage remains deferred;
  owner selected 256 MiB FAT32 for future export. No additional partition implemented.
- 2026-11-05 uncommitted — Compact 13-entry GPT, larger A allocations and fresh-install data
  reset/expansion implemented in a separate image path. FAT32 log export deferred.
  67 owner-approved focused tests pass; build/boot deferred. No old images or physical writes.
- 2026-11-05 (this commit) — Removed obsolete tools at the owner's request: the copy-only
  super migration, the parked diagnostic Linux USB (`make usb/deploy/smoke`, BusyBox pin,
  its kernel config/init/menu) and `make deploy-android`. `make update-usb` is the USB path;
  `super_candidate.py` stays because `android_fresh.py` builds the expanded disk with it.
- 2026-11-04 (this commit) — Record that bionic/linker/runtime stay a coherent generic set;
  revisit CPU-conditional selection only with measured benefit and verified early-boot safety.
- 2026-11-04 (this commit) — Folded the config-only AMD I2C-HID recipe into shared kernel
  configuration. Expanded input is byte-identical; 33 focused recipe/kernel-source tests pass.
  Richer recipes unchanged; no kernel/image rebuild or physical test needed for identical input.
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
