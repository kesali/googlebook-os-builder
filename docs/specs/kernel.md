# Kernel (GKI)

**Status:** working — Google's exact kernel rebuilt from source; Google's modules load.
**Last verified:** 2026-10-31 — `make gki`: exports identical to Google's (4501, same CRCs); `make qemu-check` passes.

## Goal
Build Google's Googlebook kernel from source with the instruction emulator compiled in, identical
enough that Google's unmodified modules (ramdisks, system_dlkm, vendor_dlkm, QEMU drivers) load.

## Current state
Verified: release `6.18.21-android17-5-g3938c8d97142-ab16302624` from tag
`android17-6.18-2026-06_r52` (commit `3938c8d97142`);
config identical to Google's except the trusted key in [kernel/gki.config](../../kernel/gki.config);
exported symbols and CRCs identical to Google's `vmlinux.symvers`; Google's certificate trusted;
Google's prebuilt virtio GPU/input/net modules load in QEMU.
Not verified: any physical-laptop driver (amdgpu, Wi-Fi, audio, touchpad).

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
- Builds fail rather than publish a kernel whose config, release string or ABI differs from Google's.

## Files
- [scripts/gki-kernel.sh](../../scripts/gki-kernel.sh) — configure, build, check, publish `out/gki/`.
- [kernel/gki.config](../../kernel/gki.config) — the complete list of config changes.
- [tools/kconfig_check.py](../../tools/kconfig_check.py), [tools/kabi_check.py](../../tools/kabi_check.py),
  [tools/kernel_certs.py](../../tools/kernel_certs.py) — config, ABI and certificate checks.
- [scripts/git-fetch.sh](../../scripts/git-fetch.sh), [scripts/pahole.sh](../../scripts/pahole.sh) — toolchain.
- [scripts/kernel-source.sh](../../scripts/kernel-source.sh) — source checkout + emulator patch.

## Verify
`make gki JOBS=12` (about an hour first time, incremental afterwards). It fails on any config,
compiler, release-string or ABI mismatch. Then `make qemu-check JOBS=12`.

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
_None agreed._

### Ideas (not approved)
- Extend instruction emulation to SSE GFNI if a userspace binary needs it (see gbos-x86 `isa_emu`).
- Laptop drivers as modules — see [laptop-hardware.md](laptop-hardware.md).
- Fill `protected_module_names_list` like Google's build (its system_dlkm module names), so
  unsigned modules cannot take over those modules' exports. Ours has always been empty.

## Handoff log
- 2026-10-31 (this commit) — Decision relaxed (owner-agreed laptop plan): built-ins are allowed for the
  first laptop boot only; larger drivers stay modules. Docs only; the config is unchanged.
- 2026-10-31 `9dfd0cf` — Google's prebuilt QEMU modules replace ours; config is Google's plus the
  trusted key (TRIM restored with Google's ABI list, vgem gone). Relink 76 s; `make qemu-check` passes.
- 2026-10-31 `d9fc850` — Kernel relinks are reproducible (`KBUILD_BUILD_VERSION=1`); modules and
  the module ramdisk are replaced only when a module changes. Checked by two forced relinks.
- 2026-10-31 `8ae83c6` — Exact GKI from source with Google's toolchain; all 4501 exports match.
