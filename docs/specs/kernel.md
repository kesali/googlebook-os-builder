# Kernel (GKI)

**Status:** partial — the source-built GKI preserves Google's ABI and selected laptop
modules build; physical driver and brightness checks remain.
**Last verified:** 2026-11-14 — `make gki` and `make android-image` passed; the build
reported 4,501 unchanged Google exports and validated the module metadata and image.

## Goal
Build Google's Googlebook kernel from source while keeping Google's modules loadable
and adding only the drivers required by selected hardware.

## Current state
The kernel is pinned to Google's Android 17 GKI release and toolchain. Build checks
require all 4,501 Google exports and CRCs to match. Laptop modules are signed with the
build's trusted key and checked against Google's helpers. QEMU uses Google's prebuilt
virtual-device modules. The owner reports the MSI and Lenovo boot without the firmware
framebuffer; the current image's physical driver behavior is not fully retested. The i915
recipe requests module loading for Intel display-class devices. GKI and image checks pass,
but generic binding and display are not hardware-verified. Google's original vendor_dlkm
contains and preloads `xe.ko` with 139 Xe aliases. `CONFIG_DRM_XE` is unset in the resolved
GKI config, but that does not remove Google's prebuilt vendor module.

## Decisions
- Keep Google's exact kernel toolchain and release. A compiler or source mismatch can
  change symbol CRCs and prevent Google's modules from loading.
- Preserve Google's export list, CRCs, certificate and `TRIM_UNUSED_KSYMS`; never
  relax ABI checks or expose the signing key.
- Use Google's prebuilt QEMU modules for the same kernel release. Sign added laptop
  modules with the trusted build key.
- Disable sysfb/simpledrm instead of keeping a custom PCI framebuffer handoff.
- Preserve Google's Xe module and aliases. The i915 alias requests module loading; the
  drivers' PCI tables and force-probe checks determine which one can bind.
- Keep the VEX instruction-emulation patch for the Zen 3 host; it covers VEX GFNI and
  AVX-VNNI, not legacy SSE GFNI.
- Keep Renoir capture-buffer compatibility separate from laptop audio routing and driver
  selection.

## Files
- [scripts/gki-kernel.sh](../../scripts/gki-kernel.sh) — configure, build and check.
- [kernel/gki.config](../../kernel/gki.config) — kernel configuration changes.
- [scripts/kernel-source.sh](../../scripts/kernel-source.sh) — pinned source and patches.
- [scripts/laptop-modules.sh](../../scripts/laptop-modules.sh),
  [kernel/laptop-modules.list](../../kernel/laptop-modules.list) — signed module set.
- [tools/kabi_check.py](../../tools/kabi_check.py) — Google ABI verification.

## Verify
Run `make gki` and require the config, release, export/CRC and module checks to pass.
For source preparation, run
`scripts/builder.sh python3 -m unittest discover -s tests -p test_kernel_source.py`.
QEMU does not verify physical AMD or Intel behavior.

## Pitfalls
- Keep `KBUILD_GENDWARFKSYMS_STABLE=1`,
  `RUSTC_FORCE_RUSTC_VERSION=rustc-android`, and `KBUILD_BUILD_VERSION=1`.
- The QEMU module is `virtio-gpu.ko`; its filename uses a hyphen.
- The source tarball is not byte-stable; use the pinned shallow Git fetch.

## Actions
- [ ] Owner checks laptop drivers and brightness — done when physical driver operation
  is reported and the brightness slider visibly changes the panel.
