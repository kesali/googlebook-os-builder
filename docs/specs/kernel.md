# Kernel (GKI)

**Status:** partial — laptop display/input/Wi-Fi/sound work; owner reports HDMI performance is now fine.
**Last verified:** 2026-11-04 — Lenovo recipe pilot: 47 focused recipe/module/overlay/touchpad/Mesa
tests pass. Expanded declarations match `eb7a787`; image build preserves all 37 recorded
output hashes/sizes, including full disk, kernel config and symbol CRCs. All 4,501 Google exports,
signed modules and filesystem metadata/fit checks pass. The 21.4 s repeat preserves timestamps
too and writes no partitions/boot files. No new QEMU or physical boot; runtime bytes unchanged.
[Evidence](../../out/hardware-recipes/).

Earlier, 2026-11-03 — PS/2 Elantech plus AR9565 candidate: 41 focused tests,
kernel/image build, all 4,501 Google exports, signed-module imports/aliases and 518
vendor_dlkm entries pass. The 20,148,224-byte vendor_dlkm fits 64 MiB. Repeat preserves all
35 recorded output/disk hashes and timestamps with no partition or boot writes.
Disposable enforcing QEMU reaches inspected setup and accessibility after input; VM exited.
[Evidence](../../out/lenovo-touchpad/). The owner subsequently confirmed Wi-Fi works and,
after the name-scoped palm calibration in `eb7a787`, touchpad movement works.
Accidental palm rejection remains unverified; see [laptop hardware](laptop-hardware.md).

Earlier, 2026-11-03 — AR9565 candidate: 40 focused tests, kernel/image build,
all 4,501 Google exports, signed-module imports/aliases and 517 vendor_dlkm entries pass.
The 20,054,016-byte vendor_dlkm fits 64 MiB. Repeat preserves hashes/timestamps of all 34
recorded outputs including the disk and writes no partitions or boot files. Disposable
enforcing QEMU reaches setup and accessibility after input (screens inspected); VM exited.
[Evidence](../../out/lenovo-wifi/). Physical Wi-Fi scanning/connection remains untested.

Earlier, 2026-11-03 — primary-alpha candidate: 33 focused tests and
`make android-image JOBS=12` pass; 4,501 Google exports unchanged, module signatures/imports
and 513 vendor_dlkm metadata entries verified. Repeat preserves all 30 recorded output/disk
hashes and timestamps with no partition/boot writes. Disposable QEMU reaches inspected setup
and responds to an accessibility tap, SELinux enforcing; VM exited.
[Evidence](../../out/intel-primary-alpha/). Lenovo hardware retest remains.

Earlier, 2026-11-02 — `make android-image JOBS=12` with the Renoir buffer patch: `kABI:
4501 Google exports, 0 missing, 0 changed`; 44 focused source/module/audio/overlay tests pass.
`make qemu-check JOBS=12` reaches setup with enforcing SELinux and stable service PIDs
([screen](../../out/qemu/screen.png), inspected). The owner's boot of `95b3bf6` had sound, and its
snapshot shows the panel as `backlight` (`sysfs_leds`, 51750 of 62451, so the HAL wrote it);
a visible brightness change was not reported. Earlier: all 5507 prior symbol versions unchanged
([previous](../../out/hardware-fixes-validation/Module.symvers-before)).

## Goal
Build Google's Googlebook kernel from source with the instruction emulator compiled in, identical
enough that Google's unmodified modules (ramdisks, system_dlkm, vendor_dlkm, QEMU drivers) load.

## Current state
Verified native-format recipe pilot: Lenovo AR9565 and Elantech options/module
paths/install entries/verified aliases now live under [hardware/](../../hardware/).
Explicit includes preserve ordering in the existing base declarations; Google's module
metadata stays a source-derived patch. The combined MSI/Lenovo image is byte-identical
to the touchpad baseline `eb7a787`, including all original safeguards and module ordering.
`make hardware-check` validates recipe wiring without building the image.

Lenovo PS/2 touchpad candidate: unchanged upstream psmouse with Elantech and normal protocol
defaults; PS/2 AUX hotplug alias `serio:ty01pr*id*ex*`, built-in libps2/I2C helpers.
No replacement of MSI's I2C-HID path, preloads or source patches. Compiled module has no
module dependencies (libps2/I2C are built in); image/ABI/repeat/QEMU checks pass above.
Physical enumeration was captured in the diagnostic logs; the owner confirms the calibrated
touchpad works. Its Android IDC and remaining palm-rejection check are in
[laptop hardware](laptop-hardware.md).

Lenovo AR9565 candidate: unchanged upstream ath9k/ath9k_hw/ath9k_common/ath modules
compile and pass the existing Google-helper import/CRC and 4,501-export checks.
Only `168c:0036` is added to hotplug metadata. Google's actual Googlebook mac80211 exports
the LED APIs (unlike the generic emulator copy); no LED/source patch or helper replacement
is needed. Signed packaging, final image/repeat/QEMU validation pass as above; physical
Wi-Fi works by subsequent owner report. [Build evidence](../../out/lenovo-wifi/).

Lenovo evidence (2026-11-03): i915 binds Broadwell and exposes `intel_backlight`;
Iris renders as HD Graphics 5500. The earlier boot failed framebuffer creation with -EINVAL.
The owner's MSI boot of the expanded image succeeds (not a full peripheral regression).
Approved candidate: reuse Churro commit `70538d7`'s
[primary-alpha patch](../../kernel/i915-gen4-primary-alpha.patch) without changing its code hunks.
Gen4-8 primaries accept Android ARGB/ABGR client targets as opaque scanout; VLV/CHV retain
native alpha, sprites/Gen9+/AMD are unchanged. Built and regression-checked as above;
the owner subsequently reaches desktop in guest/another profile and reports good performance
and video. Successful-boot logs show no framebuffer rejection; the original-profile freeze
has no retained panic trace and remains unresolved.

Verified: release `6.18.21-android17-5-g3938c8d97142-ab16302624` from tag
`android17-6.18-2026-06_r52` (commit `3938c8d97142`);
config changes are listed in [kernel/gki.config](../../kernel/gki.config): trusted key, touchpad,
simpledrm/drm_log, modular amdgpu and its display helpers, and EROFS Zstd support.
Every Google export and CRC is preserved; Google's certificate remains trusted;
Google's prebuilt virtio GPU/input/net modules load in QEMU, which still reaches the setup screen.
The thirteen AMD display, MT7922 and Renoir ACP modules in [laptop-modules.list](../../kernel/laptop-modules.list)
are stripped, signed with this build's trusted key and included in the regular Android image.
The vendor_dlkm build checks imports against Google's actual helpers; those helpers and the ABI
whitelist remain unchanged. An earlier source-tree path change caused a full rebuild and changed
all nine then-existing module hashes and the kernel bytes, not just amdgpu. No physical USB was updated.
[drm-firmware-handoff.patch](../../kernel/drm-firmware-handoff.patch) releases the firmware
framebuffer before a PCI display driver takes a DRM minor. It works with virtio in QEMU and is
based on the owner's working Churro setup; the owner subsequently reached physical setup.
[msi-backlight.patch](../../kernel/msi-backlight.patch) changes only the first panel's registered
name on the exact MSI model so Google's unchanged lights HAL can discover it.
[amdgpu-fast-flips.patch](../../kernel/amdgpu-fast-flips.patch) keeps page flips on amdgpu's fast
path when an HDMI monitor is connected (owner saw the frame rate halve); the owner subsequently
retested the updated stick and reports HDMI performance is now fine (frame rate not instrumented).

Initial driver build: four unchanged upstream Renoir ACP microphone modules, with
signatures, imports, PCI/platform aliases and dependency metadata checked against the compiled
modules. Google's existing `snd-soc-dmic` is reused byte-for-byte; the machine driver preloads
PDM DMA/DMIC. Vendor_dlkm is 17,588,224 B against Google's 18,096,128 B limit; all 511 filesystem
entries passed ownership/mode/SELinux checks. An unchanged build took 15.6 s, preserved published
output/disk timestamps and wrote no partitions ([evidence](../../out/microphone-drivers/)).

Verified on the updated laptop: the [new snapshot](../../out/laptop-boot-2026-11-02-microphone/current/hardware.txt)
shows all five ACP/DMIC modules loaded, card ID `acp`, `DMIC capture dmic-hifi-0` and
`pcmC2D0c`. After adding the route and buffer patch below, the owner reports the microphone
working on 2026-11-02. Fresh capture logs and recording-quality measurements were not supplied.
QEMU has no ACP hardware. The separate audio route is tracked in
[laptop hardware](laptop-hardware.md).

Built and checked: [renoir-capture-buffers.patch](../../kernel/renoir-capture-buffers.patch) allows
2–4 periods and a 1024-byte minimum for the desktop HAL's observed two-period buffers.
Only two Renoir header constants change; maxima, fixed DMA allocation and driver selection
are unchanged. 44 focused tests pass; the 11 min 36 s image rebuild preserves all 4501 Google
exports and all 5509 prior symbol CRCs. Signed-module checks and all 511 vendor_dlkm metadata
entries pass; its 17,588,224 B image still fits. The 18.0 s repeat preserves 29 published file
sizes/timestamps and writes no partitions or boot files. Bounded QEMU passes in 75.5 s with
enforcing SELinux and stable services; setup screenshot inspected, input not retested.
[Evidence](../../out/renoir-buffer/). The owner subsequently confirms physical microphone
functionality; generic ACP migration and other machines remain untested.

## Decisions
- Google's exact toolchain (clang r584948c, Rust 1.91.1.p3, bindgen 0.72.1, pahole 1.31 from
  source) — a different compiler changes symbol CRCs and Google's modules refuse to load.
- QEMU drivers are Google's prebuilt modules from its virtual-device build of the same release
  (`GKI_VIRT` in [sources.mk](../../sources.mk)), not compiled here. They are unsigned, so they may
  use only the exports in Google's `abi_symbollist.raw` — which ours keeps, like Google's
  (`CONFIG_TRIM_UNUSED_KSYMS`). Laptop drivers are modules too, except the few built-ins agreed for
  the first laptop boot ([laptop-hardware.md](laptop-hardware.md)); `make gki` must still show
  Google's exports and CRCs.
- Churro's [vex-emulate.patch](../../kernel/vex-emulate.patch) (vendored unchanged, content-hashed)
  emulates VEX GFNI/AVX-VNNI — Googlebook
  userspace is built for Intel Panther Lake; this Zen 3 CPU lacks those instructions.
- The source-level framebuffer handoff follows Churro's PCI display approach; errors are
  reported and abort DRM initialization. Touchpad settings and security safeguards are unchanged.
- Only DMI vendor `Micro-Star International Co., Ltd.` / model `Modern 15 B7M`, first panel:
  name the AMD backlight `backlight`, which Google's lights HAL supports. Preserve all brightness
  calculations and other machines' names. Remove this patch when the HAL supports AMD discovery.
- drm_hwcomposer allows a modeset on every commit; before DCN 3.2 amdgpu then resets all planes
  and takes the global lock, so two displays wait on each other's flips. The patch keeps that
  only when a CRTC really changes mode. Generic for DCN < 3.2 and small enough to upstream
  (the `dm_test_reset_plane_pre_dcn32_modeset` KUnit would need the same condition).
- Builds fail on unlisted config changes, a release-string mismatch, or any missing/changed
  Google export or CRC.
- New modules use the build's signing key to access protected GKI exports. Do not remove
  `TRIM_UNUSED_KSYMS`, change Google's ABI whitelist or publish the private key.
- Vendor_dlkm uses Zstd without removing Google's drivers; the new fresh layout allocates 64 MiB
  for AMD/i915 and future growth. Its decompressor must be built in before mounting it.
- Keep the Renoir buffer compatibility patch separate from MSI routing and driver selection.
  A generic ACP driver migration is separate work; drop the patch when upstream accepts these
  buffers or the old driver is replaced and verified.

## Files
- [kernel/i915-gen4-primary-alpha.patch](../../kernel/i915-gen4-primary-alpha.patch) — Churro's
  older Intel primary-plane client-target compatibility candidate.
- [scripts/gki-kernel.sh](../../scripts/gki-kernel.sh) — configure, build, check, publish `out/gki/`.
- [kernel/gki.config](../../kernel/gki.config) — the complete list of config changes.
- [tools/kconfig_check.py](../../tools/kconfig_check.py), [tools/kabi_check.py](../../tools/kabi_check.py),
  [tools/kernel_certs.py](../../tools/kernel_certs.py) — config, ABI and certificate checks.
- [scripts/git-fetch.sh](../../scripts/git-fetch.sh), [scripts/pahole.sh](../../scripts/pahole.sh) — toolchain.
- [scripts/kernel-source.sh](../../scripts/kernel-source.sh) — source checkout + the emulator patch
  and the Makefile's `KERNEL_PATCHES`, in order; a new patch hash creates a separate tree.
- [kernel/drm-firmware-handoff.patch](../../kernel/drm-firmware-handoff.patch) — early PCI
  framebuffer handoff before DRM minor allocation.
- [kernel/msi-backlight.patch](../../kernel/msi-backlight.patch) — exact-model panel naming.
- [kernel/amdgpu-fast-flips.patch](../../kernel/amdgpu-fast-flips.patch) — no full update for plain flips on DCN < 3.2.
- [kernel/renoir-capture-buffers.patch](../../kernel/renoir-capture-buffers.patch) — isolated
  Renoir capture-period compatibility candidate for the desktop audio HAL.
- [tests/test_kernel_source.py](../../tests/test_kernel_source.py) — source preparation and patch checks.
- [scripts/laptop-modules.sh](../../scripts/laptop-modules.sh), [kernel/laptop-modules.list](../../kernel/laptop-modules.list) — explicit signed-module publication.

## Verify
`make gki JOBS=12` (about an hour first time, incremental afterwards). It fails on any config,
compiler, release-string or ABI mismatch. Focused source checks:
`scripts/builder.sh python3 -m unittest discover -s tests -p test_kernel_source.py`. The one-off
[offline handoff check](../../out/framebuffer-handoff-check.py) uses a short, fresh output
directory, for example `scripts/builder.sh python3 out/framebuffer-handoff-check.py out/fb4`.
Inspect the screenshots; this does not verify AMD hardware.

## Pitfalls
- `KBUILD_GENDWARFKSYMS_STABLE=1` and `RUSTC_FORCE_RUSTC_VERSION=rustc-android` are required,
  otherwise symbol CRCs / Rust export names differ from Google's.
- The module file is `virtio-gpu.ko` (hyphen), not `virtio_gpu.ko`.
- The gitiles source tarball is not byte-stable; the kernel comes from a shallow Git fetch checked against the commit.
- Lazy Git fetches of huge toolchain blobs can stall for many minutes; `git-fetch.sh` downloads files from gitiles and verifies them with Git instead.
- Legacy SSE-encoded GFNI (`66 0f 38 cf`) still raises SIGILL; only VEX encodings are emulated.
- `KBUILD_BUILD_VERSION=1` (Google's `#1`) keeps relinks reproducible; without it, Kbuild counts
  links and each relink produces a different kernel.
- The config step's hash includes `gki-kernel.sh`, so any edit to it (even a comment) reconfigures
  and relinks (about 50 s).

## Actions
- [ ] Check the brightness slider — done when the owner confirms it changes the panel
  (the snapshot already shows the expected `backlight` name and label).

### Ideas (not approved)
- Extend instruction emulation to SSE GFNI if a userspace binary needs it (see gbos-x86 `isa_emu`).
- Further laptop drivers as modules — see [laptop-hardware.md](laptop-hardware.md).
- Fill `protected_module_names_list` like Google's build (its system_dlkm module names), so
  unsigned modules cannot take over those modules' exports. Ours has always been empty.

## Handoff log
- 2026-11-04 (this commit) — Native-format AR9565/Elantech recipes retain explicit Google patches.
  47 tests, exact effective declarations, image/ABI/module/metadata checks and 37-output binary
  equality/no-write repeat pass. No new QEMU/hardware boot; owner-confirmed baseline preserved.
- 2026-11-03 (this commit) — Upstream psmouse/Elantech packaged with compiled PS/2 alias
  and built-in helpers; dependency check corrected an unnecessary SMBus-module entry.
  41 tests/build/ABI/image/no-write repeat and enforcing QEMU setup/input pass; hardware pending.
- 2026-11-03 (this commit) — Upstream AR9565 ath9k needs no source patch: actual Googlebook
  mac80211 exports LED APIs. Four signed modules/exact alias pass 40 tests, build/kABI/import/
  metadata checks, no-write repeat and enforcing QEMU setup/input. Physical Wi-Fi retest remains.
- 2026-11-03 (this commit) — Reused Churro's primary-alpha fix for Lenovo fb -22. 33 tests,
  build/kABI/module/metadata checks, no-write repeat and enforcing QEMU setup/input pass
  (screens inspected). Lenovo retest pending; MSI pre-patch boot owner-confirmed; USB untouched.
- 2026-11-03 (this commit) — Signed i915/intel-gtt and sole Broadwell alias included in the fresh
  64 MiB vendor_dlkm; all 4,501 Google exports and image checks pass. Enforcing direct/UEFI QEMU
  verified; physical i915 binding and MSI regression remain owner tests.
- 2026-11-03 `uncommitted` — Final i915/intel-gtt metadata/signatures and sole 8086:1616 alias
  pass checks in a separate 32 MiB vendor_dlkm; 69 focused tests and enforcing direct/UEFI QEMU
  pass. Existing disk/USB untouched; old-layout builds remain blocked, physical GPUs untested.
- 2026-11-03 `uncommitted` — Enlarged disposable vendor_dlkm allocation to 32 MiB; Zstd-9
  i915 candidate fits at 19,636,224 B with 513 entries verified. Separate upstream-generated
  super passes metadata/payload checks; no Iris, runtime test or working-disk/USB migration yet.
- 2026-11-03 `uncommitted` — Broadwell i915/intel-gtt build preserves all 4501 Google exports;
  signed modules pass unchanged-helper checks. Disposable vendor_dlkm verifies 513 entries but
  exceeds its 18,096,128 B limit even at Zstd 22 (18,259,968 B). No disk/USB update; Intel blocked.
- 2026-11-03 (this commit) — Vendored the exact cached Churro emulator patch after its source
  repository was deleted. All 16 `test_kernel_source` tests pass in the builder;
  `make -n sources JOBS=12` is a no-op, and bytes match the pinned SHA. No build, boot or USB write.
- 2026-11-02 `uncommitted` — Owner confirms microphone works after the Renoir buffer update.
  Driver, named InternalMic route and isolated buffer patch now have owner hardware confirmation;
  no new capture logs or recording-quality measurements supplied.
- 2026-11-02 (this commit) — Isolated Renoir buffer patch passes 44 tests, build/kABI/module/
  metadata/fit checks, no-write repeat and enforcing QEMU (screen inspected). Driver selection/
  routing unchanged. Owner USB update and actual recording test pending.
- 2026-11-02 (this commit) — Updated laptop snapshot confirms ACP/DMIC modules, `acp` card and
  DMIC capture PCM. Owner reports app recording still unavailable; separate InternalMic routing
  approved and in progress, not a further kernel-driver change.
- 2026-11-02 (this commit) — Upstream Renoir ACP modules built/signed; Google DMIC reused.
  29 tests, 4501-export kABI, image metadata/fit, no-write repeat and enforcing QEMU pass.
  Laptop capture-device check pending; audio routes unchanged, no physical USB write.
- 2026-11-02 (this commit) — Owner retested the updated stick: HDMI works and performance seems
  fine. Removed the subjective HDMI retest action; no instrumented frame-rate measurement.
- 2026-11-02 (this commit) — amdgpu fast flips with HDMI; `kernel-source.sh` takes a patch list.
  kABI clean, 11 source tests (incl. a compiled model of the condition) and enforcing QEMU pass.
  Next: owner retests HDMI frame rate on the laptop.
- 2026-11-02 `95b3bf6` — MSI-only backlight name patch built; 4501 Google exports and 5507
  previous symbol versions unchanged. Exact DMI/first-panel naming tests and enforcing QEMU pass.
  Laptop handoff/Wi-Fi are owner-confirmed; new physical brightness behavior awaits retest.
- 2026-11-02 `uncommitted` — Churro-based handoff passes ABI and offline QEMU checks; the owner
  updated the USB and read-back matched. Original disk preserved; laptop AMD remains untested.
- 2026-11-01 (this commit) — Added modular AMD display support and EROFS Zstd; Google's 4501
  exports/CRCs and ABI whitelist are preserved. Four signed modules built; UEFI checks pass.
  Physical device binding and display remain unverified.
- 2026-11-01 (this commit) — Added the M1 built-ins to `gki.config` (18 settings: 6 touchpad, 12
  screen log incl. selected ones). First `make gki` passed config and ABI checks (69 s); QEMU still boots.
- 2026-10-31 `9c78a5d` — Decision relaxed (owner-agreed laptop plan): built-ins are allowed for the
  first laptop boot only; larger drivers stay modules. Docs only; the config is unchanged.
- 2026-10-31 `9dfd0cf` — Google's prebuilt QEMU modules replace ours; config is Google's plus the
  trusted key (TRIM restored with Google's ABI list, vgem gone). Relink 76 s; `make qemu-check` passes.
- 2026-10-31 `d9fc850` — Kernel relinks are reproducible (`KBUILD_BUILD_VERSION=1`); modules and
  the module ramdisk are replaced only when a module changes. Checked by two forced relinks.
- 2026-10-31 `8ae83c6` — Exact GKI from source with Google's toolchain; all 4501 exports match.
