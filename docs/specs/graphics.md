# Graphics

**Status:** working (softpipe, slow) — real setup UI at 1280x720, CPU-rendered.
**Last verified:** 2026-10-31 — `make qemu-check` + manual screenshot `out/qemu/input-screen.png`; SurfaceFlinger reports softpipe.

## Goal
Show Googlebook OS on screen. First correctness (softpipe),
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
  [android/system_ext/dali-qemu.rc](../../android/system_ext/dali-qemu.rc), not Android properties (name-length limits).
- [android/mesa-drm-master.patch](../../android/mesa-drm-master.patch): Mesa drops DRM master after
  opening the primary node, so the composer can drive the display. A source patch, no added privileges.
- Only virtio-gpu is loaded (no vgem). Graphics properties: [android/vendor/build-prop.patch](../../android/vendor/build-prop.patch);
  DRM node labels: [android/vendor/file-contexts.patch](../../android/vendor/file-contexts.patch).
- No host-GPU passthrough.

## Files
- [scripts/mesa.sh](../../scripts/mesa.sh) — Mesa/libdrm/Expat build; build cache keyed by inputs.
- [scripts/ndk.sh](../../scripts/ndk.sh), [scripts/source.sh](../../scripts/source.sh) — NDK and patched source trees.
- [android/mesa-drm-master.patch](../../android/mesa-drm-master.patch) — Mesa source patch.
- [android/vendor/install.list](../../android/vendor/install.list), [android/vendor/build-prop.patch](../../android/vendor/build-prop.patch) — Mesa libraries and settings in vendor.

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
- `mesa.sh` runs `meson setup` and CMake only when it or `cross.ini` changes (hash in
  `out/mesa/build-*/settings`); Ninja reconfigures by itself when an upstream build file changes.
- `drm.debug=0x1 ignore_loglevel` on the command line shows DRM open/master events — remove after diagnosing.

## Actions
- [ ] Plan accelerated rendering in QEMU (e.g. virgl or Venus with host Mesa) — done when
  options, trade-offs and a recommendation are agreed with the user. Not approved to implement.

### Ideas (not approved)
- llvmpipe instead of softpipe as a cheaper speed-up (needs LLVM for Android).
- RADV/radeonsi + minigbm for the laptop's AMD GPU — see [laptop-hardware.md](laptop-hardware.md).

## Handoff log
- 2026-10-31 (this commit) — Meson and CMake configure only when their settings change; no-op Mesa
  step 3.7 s → 1.5 s.
- 2026-10-31 `357470d` — Graphics properties and DRM labels are now patches (build-prop.patch, file-contexts.patch); Mesa files in android/vendor/install.list.
- 2026-10-31 `56719c0` — Mesa softpipe from source; DRM-master patch gives real scanout; setup UI visible.
