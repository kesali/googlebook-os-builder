# Kernel (GKI)

**Status:** partial — laptop display/input/Wi-Fi work; the backlight candidate needs a physical test.
**Last verified:** 2026-11-02 — `make android-image JOBS=12` rebuilt the patched kernel/modules:
all 4501 Google exports/CRCs and all 5507 prior symbol-version records are unchanged
([build log](../../out/hardware-fixes-validation/build.log),
[previous symbols](../../out/hardware-fixes-validation/Module.symvers-before),
[current symbols](../../out/gki/build/Module.symvers)). Enforcing QEMU reaches setup; a repeat
build preserves published timestamps. The owner previously completed physical setup with input
and Wi-Fi. The new AMD backlight name is not yet physically verified.

## Goal
Build Google's Googlebook kernel from source with the instruction emulator compiled in, identical
enough that Google's unmodified modules (ramdisks, system_dlkm, vendor_dlkm, QEMU drivers) load.

## Current state
Verified: release `6.18.21-android17-5-g3938c8d97142-ab16302624` from tag
`android17-6.18-2026-06_r52` (commit `3938c8d97142`);
config changes are listed in [kernel/gki.config](../../kernel/gki.config): trusted key, touchpad,
simpledrm/drm_log, modular amdgpu and its display helpers, and EROFS Zstd support.
Every Google export and CRC is preserved; Google's certificate remains trusted;
Google's prebuilt virtio GPU/input/net modules load in QEMU, which still reaches the setup screen.
The nine AMD display and MT7922 modules in [laptop-modules.list](../../kernel/laptop-modules.list)
are stripped, signed with this build's trusted key and included in the regular Android image.
The vendor_dlkm build checks imports against Google's actual helpers; those helpers and the ABI
whitelist remain unchanged. The new source-tree path caused a full rebuild and changed all nine
module hashes and the kernel bytes, not just amdgpu. No physical USB was updated.
[drm-firmware-handoff.patch](../../kernel/drm-firmware-handoff.patch) releases the firmware
framebuffer before a PCI display driver takes a DRM minor. It works with virtio in QEMU and is
based on the owner's working Churro setup; the owner subsequently reached physical setup.
[msi-backlight.patch](../../kernel/msi-backlight.patch) changes only the first panel's registered
name on the exact MSI model so Google's unchanged lights HAL can discover it.

## Decisions
- Google's exact toolchain (clang r584948c, Rust 1.91.1.p3, bindgen 0.72.1, pahole 1.31 from
  source) — a different compiler changes symbol CRCs and Google's modules refuse to load.
- QEMU drivers are Google's prebuilt modules from its virtual-device build of the same release
  (`GKI_VIRT` in [sources.mk](../../sources.mk)), not compiled here. They are unsigned, so they may
  use only the exports in Google's `abi_symbollist.raw` — which ours keeps, like Google's
  (`CONFIG_TRIM_UNUSED_KSYMS`). Laptop drivers are modules too, except the few built-ins agreed for
  the first laptop boot ([laptop-hardware.md](laptop-hardware.md)); `make gki` must still show
  Google's exports and CRCs.
- Churro's `vex-emulate.patch` (downloaded, SHA-pinned) emulates VEX GFNI/AVX-VNNI — Googlebook
  userspace is built for Intel Panther Lake; this Zen 3 CPU lacks those instructions.
- The source-level framebuffer handoff follows Churro's PCI display approach; errors are
  reported and abort DRM initialization. Touchpad settings and security safeguards are unchanged.
- Only DMI vendor `Micro-Star International Co., Ltd.` / model `Modern 15 B7M`, first panel:
  name the AMD backlight `backlight`, which Google's lights HAL supports. Preserve all brightness
  calculations and other machines' names. Remove this patch when the HAL supports AMD discovery.
- Builds fail on unlisted config changes, a release-string mismatch, or any missing/changed
  Google export or CRC.
- New modules use the build's signing key to access protected GKI exports. Do not remove
  `TRIM_UNUSED_KSYMS`, change Google's ABI whitelist or publish the private key.
- Vendor_dlkm uses Zstd to fit the additional modules without removing Google's drivers or
  resizing partitions; its decompressor must be built in before that filesystem is mounted.

## Files
- [scripts/gki-kernel.sh](../../scripts/gki-kernel.sh) — configure, build, check, publish `out/gki/`.
- [kernel/gki.config](../../kernel/gki.config) — the complete list of config changes.
- [tools/kconfig_check.py](../../tools/kconfig_check.py), [tools/kabi_check.py](../../tools/kabi_check.py),
  [tools/kernel_certs.py](../../tools/kernel_certs.py) — config, ABI and certificate checks.
- [scripts/git-fetch.sh](../../scripts/git-fetch.sh), [scripts/pahole.sh](../../scripts/pahole.sh) — toolchain.
- [scripts/kernel-source.sh](../../scripts/kernel-source.sh) — source checkout + emulator,
  framebuffer handoff and backlight patches; a new patch hash creates a separate tree.
- [kernel/drm-firmware-handoff.patch](../../kernel/drm-firmware-handoff.patch) — early PCI
  framebuffer handoff before DRM minor allocation.
- [kernel/msi-backlight.patch](../../kernel/msi-backlight.patch) — exact-model panel naming.
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
- [ ] Check backlight discovery on the laptop — done when the owner confirms the brightness
  slider changes the panel and the snapshot shows the expected name/label.

### Ideas (not approved)
- Extend instruction emulation to SSE GFNI if a userspace binary needs it (see gbos-x86 `isa_emu`).
- Further laptop drivers as modules — see [laptop-hardware.md](laptop-hardware.md).
- Fill `protected_module_names_list` like Google's build (its system_dlkm module names), so
  unsigned modules cannot take over those modules' exports. Ours has always been empty.

## Handoff log
- 2026-11-02 (this commit) — MSI-only backlight name patch built; 4501 Google exports and 5507
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
