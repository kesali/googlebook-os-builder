# Graphics

**Status:** partial — QEMU softpipe works; the laptop's desktop runs on AMD, with apps on RADV.
**Last verified:** 2026-11-02 — the owner completed setup on the laptop and finds apps and
graphics fast. That boot's log ([android.log](../../out/laptop-boot-2026-11-02-hdmi/current/))
shows Chrome's ANGLE on `Vulkan 1.1.363 (AMD Radeon Graphics (RADV RENOIR) (0x000015E7))`;
SurfaceFlinger and HWUI do not log their renderer. Earlier,
an offline disposable UEFI boot handed simpledrm card0 to
virtio-gpu; the [setup screen](../../out/fb2/android-uefi-console-g0b93ipe/before-input.png)
and [mouse-opened dialog](../../out/fb2/android-uefi-console-g0b93ipe/after-input.png) were
inspected. SurfaceFlinger reports softpipe and SELinux is enforcing. Setup was not completed.
A separate firmware-free QEMU graphics boot also reached
[setup](../../out/fb3/android-uefi-graphics-tlovd2in/screen.png).

## Goal
Show Googlebook OS on screen. First correctness (softpipe),
then speed (accelerated rendering), later the laptop's AMD GPU.

## Current state
Verified: source-built Mesa and minigbm work with Google's unchanged composer, allocator service
and mapper on virtio-gpu. RADV/Zink and the AMD allocator backend build; all 49 gralloc and 22 GBM
exports used by Google's clients are present. The prior laptop kernel loaded amdgpu as DRM minor 1,
but SurfaceFlinger repeatedly reported invalid present fences. The
[source-level handoff](../../kernel/drm-firmware-handoff.patch) gives virtio card0 in QEMU and a
visible setup screen on the laptop. On the laptop, Chrome renders through ANGLE on RADV; which
renderer SurfaceFlinger and HWUI use, and the frame rate, are not measured. QEMU is still CPU-rendered.

## Decisions
- Owner's overnight request authorizes an AMD test candidate, retaining softpipe as the verified fallback.
- Mesa 26.3.0-rc3, libdrm 2.4.133, Expat 2.7.3 from source, NDK r30 at API 35;
  softpipe, Zink and RADV with ACO, no LLVM/GLX. libdrm, Expat and Mesa's C++ runtime are linked statically to avoid
  vendor linker-namespace problems. Pins: [sources.mk](../../sources.mk).
- Software rendering is selected with `LIBGL_ALWAYS_SOFTWARE`/`GALLIUM_DRIVER` in
  [graphics-softpipe.rc](../../android/system_ext/graphics-softpipe.rc), not Android properties (name-length limits).
- The laptop menu selects AMD only for PCI `1002:15e7`; otherwise softpipe is the default.
  [graphics-amd.rc](../../android/system_ext/graphics-amd.rc) selects Google's ANGLE GLES,
  RADV Vulkan RenderEngine and Mesa GBM/Zink, with GL HWUI like QEMU. Vulkan HWUI needs a
  downstream RADV two-queue patch (Churro); it is shelved while GL HWUI displays setup.
- LineageOS minigbm's Mesa backend needs the small AMD/FD/mapping fixes in
  [minigbm-amd.patch](../../android/minigbm-amd.patch). Its C++ interface links to Google's actual
  platform libraries, not NDK libc++; an ABI gate checks Google's clients whenever either image or library changes.
- [android/mesa-drm-master.patch](../../android/mesa-drm-master.patch): Mesa drops DRM master after
  opening the primary node, so the composer can drive the display. A source patch, no added privileges.
- QEMU loads Google's virtio-gpu; the laptop adds amdgpu with official firmware.
  Graphics properties: [android/vendor/build-prop.patch](../../android/vendor/build-prop.patch);
  DRM node labels: [android/vendor/file-contexts.patch](../../android/vendor/file-contexts.patch).
- Live uevents are serialized to prevent a delayed simpledrm remove event deleting amdgpu's reused
  card0. Only the MSI GPU's identification files get an existing SELinux type (`sysfs_gpu`, the
  same file set Google labels for its own GPU); no allow rules change.
- Use Churro's earlier PCI framebuffer handoff so the real GPU can take card0; preserve
  simpledrm for early output. It affects PCI display drivers in QEMU as well as the laptop.
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
- libdrm reads the GPU's `uevent`, `vendor`, `device` and `subsystem_*` sysfs files and skips the
  GPU if any read is denied. Then Mesa logs `Failed to open any DRM device`, SurfaceFlinger aborts
  (`Failed to create a valid texture`) and init restarts it in a loop. Label all of them.
- drm_hwcomposer reads `vendor.hwc.use_log_gamma_lut`, not a `vendor.hwc.drm.` name. Google sets
  it for xe; on amdgpu the composer then logged a missing `LOG_GAMMA_LUT` every frame (58 lines/s
  on the laptop, filling the persistent log in under a minute). The build-prop patch turns it off.
- Mesa uses `meson.options`, not `meson_options.txt`.
- `--wrap-mode=nofallback` stops Meson silently using Mesa's bundled older Expat.
- Editing a Mesa/minigbm patch or the source-extraction script changes the source directory name,
  so a fresh tree is extracted; edits made directly in the old tree are not carried over.
- `mesa.sh` runs `meson setup` and CMake only when it or `cross.ini` changes (hash in
  `out/mesa/build-*/settings`); Ninja reconfigures by itself when an upstream build file changes.
- `drm.debug=0x1 ignore_loglevel` on the command line shows DRM open/master events — remove after diagnosing.
- Meson strips even skipped install targets. Install into the build cache, then publish only changed
  bytes; otherwise an unchanged build rewrites library timestamps.

## Actions
- [x] Validate the handoff on the laptop — the owner saw the setup screen and used the touchpad.
- [ ] Confirm the laptop compositor and HWUI renderer — done when SurfaceFlinger's or HWUI's
  output from a laptop boot names ANGLE/RADV rather than a software renderer (apps already do).
- [ ] Plan accelerated rendering in QEMU (e.g. virgl or Venus with host Mesa) — done when
  options, trade-offs and a recommendation are agreed with the user. Not approved to implement.

### Ideas (not approved)
- llvmpipe instead of softpipe as a cheaper speed-up (needs LLVM for Android).
- Vulkan HWUI with Churro's RADV two-queue patch, if GL HWUI proves slow on the laptop.

## Handoff log
- 2026-11-02 (this commit) — Laptop log reviewed: Chrome's ANGLE runs on RADV RENOIR. Setup
  completed there; SurfaceFlinger/HWUI renderer still to confirm (`dumpsys SurfaceFlinger`).
- 2026-11-02 `2ee6da9` — Composer log-gamma property corrected; built vendor `build.prop`
  checked. With the color pipeline off this only removes the per-frame log; laptop log not yet rechecked.
- 2026-11-02 `uncommitted` — Laptop USB boot shows the setup screen with the touchpad working.
  A Vulkan HWUI draft was shelved (owner's choice) because GL HWUI already displays.
- 2026-11-02 `uncommitted` — Offline QEMU handoff, setup and mouse click pass with enforcing
  SELinux. The owner installed the kernel on the USB; laptop AMD remains untested.
- 2026-11-01 `uncommitted` — Physical logs show amdgpu initializes but no UI appears. An
  opt-in GRUB test for the possible card0 gap passes a QEMU shell check but panicked on the laptop.
- 2026-11-01 (this commit) — The laptop GPU's sysfs labels covered only `uevent`, so SurfaceFlinger
  crash-looped on the laptop; now all identification files are labelled. Verified in QEMU at the
  laptop's PCI path (softpipe). AMD rendering is still untested.
- 2026-11-01 `54771be` — Built RADV/Zink and an ABI-checked AMD allocator, kept softpipe.
  UEFI setup still renders under enforcing SELinux; wrapper and timestamp regressions pass.
  AMD display/performance require the owner's laptop test.
- 2026-10-31 (this commit) — Meson and CMake configure only when their settings change; no-op Mesa
  step 3.7 s → 1.5 s.
- 2026-10-31 `357470d` — Graphics properties and DRM labels are now patches (build-prop.patch, file-contexts.patch); Mesa files in android/vendor/install.list.
- 2026-10-31 `56719c0` — Mesa softpipe from source; DRM-master patch gives real scanout; setup UI visible.
