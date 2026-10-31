# Graphics

**Status:** working (softpipe, slow) — real setup UI at 1280x720, CPU-rendered.
**Last verified:** 2026-10-31 — `make qemu-check` + manual screenshot `out/qemu/input-screen.png`; SurfaceFlinger reports softpipe.

## Goal
Show Googlebook OS on screen using graphics built from source. First correctness (softpipe),
then speed (accelerated rendering), later the laptop's AMD GPU.

## Current state
Verified: Mesa EGL/GLES softpipe built from source with the NDK; Google's DRM composer and
minigbm unmodified; virtio-gpu scanout of the welcome and language screens.
Not verified / not done: acceptable performance, Vulkan, hardware acceleration, AMD GPU.

## Decisions
- Mesa 26.3.0-rc3, libdrm 2.4.133, Expat 2.7.3 from source, NDK r30 at API 35; softpipe only;
  no LLVM/Vulkan/GLX. libdrm, Expat and the C++ runtime are linked statically to avoid
  vendor linker-namespace problems. Pins: [sources.mk](../../sources.mk).
- Software rendering is selected with `LIBGL_ALWAYS_SOFTWARE`/`GALLIUM_DRIVER` in
  [android/dali-qemu.rc](../../android/dali-qemu.rc), not Android properties (name-length limits).
- [android/mesa-drm-master.patch](../../android/mesa-drm-master.patch): Mesa drops DRM master after
  opening the primary node, so the composer can drive the display. A source patch, no added privileges.
- Only virtio-gpu is loaded (no vgem). Graphics properties: [android/vendor.props](../../android/vendor.props).
- No host-GPU passthrough.

## Files
- [scripts/mesa.sh](../../scripts/mesa.sh) — Mesa/libdrm/Expat build; build cache keyed by inputs.
- [scripts/ndk.sh](../../scripts/ndk.sh), [scripts/source.sh](../../scripts/source.sh) — NDK and patched source trees.
- [android/mesa-drm-master.patch](../../android/mesa-drm-master.patch), [android/vendor.props](../../android/vendor.props).

## Verify
`make mesa JOBS=12`, then `make qemu-check JOBS=12`. Open `out/qemu/screen.png` and look at it:
a correctly sized image can still be QEMU's "Display output is not active" placeholder.
`out/qemu/surfaceflinger.txt` should name softpipe and the QEMU Monitor display.

## Pitfalls
- Symptom of the DRM-master problem: composer logs `Failed to set drm master` / `No pipelines
  available. Creating null-display`, and QEMU shows "Display output is not active".
- Mesa uses `meson.options`, not `meson_options.txt`.
- `--wrap-mode=nofallback` stops Meson silently using Mesa's bundled older Expat.
- Editing the patch changes the source directory name (patch hash), so a fresh tree is extracted; edits made directly in the old tree are not carried over.
- `drm.debug=0x1 ignore_loglevel` on the command line shows DRM open/master events — remove after diagnosing.

## Actions
- [ ] Plan accelerated rendering in QEMU (e.g. virgl or Venus with host Mesa) — done when
  options, trade-offs and a recommendation are agreed with the user. Not approved to implement.

### Ideas (not approved)
- llvmpipe instead of softpipe as a cheaper speed-up (needs LLVM for Android).
- RADV/radeonsi + minigbm for the laptop's AMD GPU — see [laptop-hardware.md](laptop-hardware.md).

## Handoff log
- 2026-10-31 `56719c0` — Mesa softpipe from source; DRM-master patch gives real scanout; setup UI visible.
