# Kernel (GKI)

**Status:** working — Google's exact kernel rebuilt from source; Google's modules load.
**Last verified:** 2026-10-31 — `make gki`: all 4501 of Google's exported symbols match; Android boots in QEMU.

## Goal
Build Google's Googlebook kernel from source, identical enough that Google's signed, unmodified
modules (ramdisks, system_dlkm, vendor_dlkm) still load, plus a short, listed set of extra drivers.

## Current state
Verified: release `6.18.21-android17-5-g3938c8d97142-ab16302624` from tag
`android17-6.18-2026-06_r52` (commit `3938c8d97142`);
config identical to Google's except [kernel/gki.config](../../kernel/gki.config); symbol CRCs match;
Google's certificate trusted; virtio GPU/input/net modules load in QEMU.
Not verified: any physical-laptop driver (amdgpu, Wi-Fi, audio, touchpad).

## Decisions
- Google's exact toolchain (clang r584948c, Rust 1.91.1.p3, bindgen 0.72.1, pahole 1.31 from
  source) — a different compiler changes symbol CRCs and Google's modules refuse to load.
- Extra drivers are **modules only**, so the kernel image and every symbol CRC stay Google's.
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
- The GKI script reinstalls modules every run; later steps normalise timestamps so this causes no rebuild.

## Actions
- [ ] Decide on vgem — it is built (`CONFIG_DRM_VGEM=m`) but no longer loaded, and its comment in
  `gki.config` is stale. Done when it is removed or the comment states why it stays.

### Ideas (not approved)
- Extend instruction emulation to SSE GFNI if a userspace binary needs it (see gbos-x86 `isa_emu`).
- Laptop drivers as modules — see [laptop-hardware.md](laptop-hardware.md).

## Handoff log
- 2026-10-31 `8ae83c6` — Exact GKI from source with Google's toolchain; all 4501 exports match.
