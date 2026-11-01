# Graphics

**Status:** partial — QEMU softpipe works; the AMD stack is built, awaiting the laptop.
**Last verified:** 2026-11-01 — `make android-uefi-check JOBS=12`: the
[setup screen](../../out/android-uefi-graphics-pgfv692u/screen.png) was inspected;
SurfaceFlinger reports softpipe. `make test minigbm-check`: 59 Python tests and GBM failure checks pass.
The disposable direct-kernel check also selected the default profile and its
[virtual mouse opened a dialog](../../out/overnight/direct/mouse-click.png).

## Goal
Show Googlebook OS on screen. First correctness (softpipe),
then speed (accelerated rendering), later the laptop's AMD GPU.

## Current state
Verified: source-built Mesa and minigbm work with Google's unchanged composer, allocator service
and mapper on virtio-gpu. RADV/Zink and the AMD allocator backend build; all 49 gralloc and 22 GBM
exports used by Google's clients are present. Not verified: AMD rendering, framebuffer handoff,
Vulkan at runtime or acceptable laptop performance. QEMU is still CPU-rendered.

## Decisions
- Owner's overnight request authorizes an AMD test candidate, retaining softpipe as the verified fallback.
- Mesa 26.3.0-rc3, libdrm 2.4.133, Expat 2.7.3 from source, NDK r30 at API 35;
  softpipe, Zink and RADV with ACO, no LLVM/GLX. libdrm, Expat and Mesa's C++ runtime are linked statically to avoid
  vendor linker-namespace problems. Pins: [sources.mk](../../sources.mk).
- Software rendering is selected with `LIBGL_ALWAYS_SOFTWARE`/`GALLIUM_DRIVER` in
  [graphics-softpipe.rc](../../android/system_ext/graphics-softpipe.rc), not Android properties (name-length limits).
- The laptop menu selects AMD only for PCI `1002:15e7`; otherwise softpipe is the default.
  [graphics-amd.rc](../../android/system_ext/graphics-amd.rc) selects Google's ANGLE GLES,
  RADV Vulkan RenderEngine and Mesa GBM/Zink. HWUI stays GL: Vulkan HWUI would require another
  downstream RADV queue patch, which we do not carry.
- LineageOS minigbm's Mesa backend needs the small AMD/FD/mapping fixes in
  [minigbm-amd.patch](../../android/minigbm-amd.patch). Its C++ interface links to Google's actual
  platform libraries, not NDK libc++; an ABI gate checks Google's clients whenever either image or library changes.
- [android/mesa-drm-master.patch](../../android/mesa-drm-master.patch): Mesa drops DRM master after
  opening the primary node, so the composer can drive the display. A source patch, no added privileges.
- QEMU loads Google's virtio-gpu; the laptop adds amdgpu with official firmware.
  Graphics properties: [android/vendor/build-prop.patch](../../android/vendor/build-prop.patch);
  DRM node labels: [android/vendor/file-contexts.patch](../../android/vendor/file-contexts.patch).
- Live uevents are serialized to prevent a delayed simpledrm remove event deleting amdgpu's reused
  card0. Only the MSI GPU's identification path gets an existing SELinux type; no allow rules change.
- No host-GPU passthrough.

## Files
- [scripts/mesa.sh](../../scripts/mesa.sh) — Mesa/libdrm/Expat build; build cache keyed by inputs.
- [scripts/minigbm.sh](../../scripts/minigbm.sh), [tools/minigbm_abi.py](../../tools/minigbm_abi.py) — incremental allocator build and platform ABI gate.
- [tests/gbm-wrapper.c](../../tests/gbm-wrapper.c), [tests/test_mesa.py](../../tests/test_mesa.py) — FD/error handling and unchanged-output publication.
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
- Meson strips even skipped install targets. Install into the build cache, then publish only changed
  bytes; otherwise an unchanged build rewrites library timestamps.

## Actions
- [ ] Plan accelerated rendering in QEMU (e.g. virgl or Venus with host Mesa) — done when
  options, trade-offs and a recommendation are agreed with the user. Not approved to implement.

- [ ] Validate AMD scanout and input on the laptop — done when an inspected screen/photo and
  real interaction demonstrate usable setup; module compilation is not proof of graphics.

### Ideas (not approved)
- llvmpipe instead of softpipe as a cheaper speed-up (needs LLVM for Android).

## Handoff log
- 2026-11-01 (this commit) — Built RADV/Zink and an ABI-checked AMD allocator, kept softpipe.
  UEFI setup still renders under enforcing SELinux; wrapper and timestamp regressions pass.
  AMD display/performance require the owner's laptop test.
- 2026-10-31 (this commit) — Meson and CMake configure only when their settings change; no-op Mesa
  step 3.7 s → 1.5 s.
- 2026-10-31 `357470d` — Graphics properties and DRM labels are now patches (build-prop.patch, file-contexts.patch); Mesa files in android/vendor/install.list.
- 2026-10-31 `56719c0` — Mesa softpipe from source; DRM-master patch gives real scanout; setup UI visible.
