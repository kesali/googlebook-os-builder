# Graphics

**Status:** partial — QEMU softpipe passes and the owner reports MSI graphics work on
Mesa 26.3.0; the camera is not detected and shows a black screen.
**Last verified:** 2026-11-13 — five focused tests, image checks, no-write repeat and
QEMU softpipe pass.

## Goal
Provide a reliable software-rendering fallback, then hardware graphics for the laptops.

## Current state
Mesa 26.3.0 is source-built with RADV/Zink for AMD, hasvk for Broadwell Intel and
softpipe for QEMU. The owner reports the MSI graphics work on this image; the active
SurfaceFlinger/HWUI renderer was not supplied. The owner reports the camera is not
detected and shows a black screen. Its cause and a software camera fallback are unknown.
The Lenovo profile exists, but no current-image hardware retest was reported.

## Decisions
- Keep softpipe as the verified QEMU fallback. Build Mesa without LLVM; RADV uses ACO.
- Select the AMD profile only for MSI PCI ID `1002:15e7`. Keep GL HWUI: Google's Vulkan
  HWUI requires two queues, while RADV exposes one. Keep RADV for Vulkan RenderEngine.
- Use upstream `android-strict=false` for native RADV/hasvk capabilities. This affects
  all RADV clients, so do not claim CTS or app compatibility without testing.
- Do not ship the separate RadeonSI VA-API camera driver or shared AMD helper. Camera
  operation after their removal is not established.
- Retain the source patches for DRM-master release, RADV YV12/AHB queries and aligned
  planar pitches. Preserve Google's allocator/composer ABI checks.
- Use minigbm's upstream property-based Mesa selection. Do not add host-GPU passthrough.

## Files
- [sources.mk](../../sources.mk) — pinned Mesa, libdrm and Expat.
- [scripts/mesa.sh](../../scripts/mesa.sh) and
  [scripts/minigbm.sh](../../scripts/minigbm.sh) — graphics builds.
- [hardware/drivers/drm-handoff/mesa-drm-master.patch](../../hardware/drivers/drm-handoff/mesa-drm-master.patch) —
  composer/display handoff.
- [hardware/drivers/amdgpu/mesa-radv-yv12.patch](../../hardware/drivers/amdgpu/mesa-radv-yv12.patch)
  and [minigbm-yuv-pitch.patch](../../hardware/drivers/amdgpu/minigbm-yuv-pitch.patch) —
  video buffer compatibility.
- [hardware/msi-modern-15-b7m/system_ext/graphics-amd.rc](../../hardware/msi-modern-15-b7m/system_ext/graphics-amd.rc) —
  MSI profile.

## Verify
Run `make test`, `make mesa`, `make android-image` and `make qemu-check`. Inspect the
QEMU screenshot and confirm softpipe; neither proves physical GPU or camera behavior.
On the laptop, inspect SurfaceFlinger/HWUI renderer logs and camera logs.

## Pitfalls
- Missing labels on GPU `uevent`, vendor, device or subsystem files can make libdrm skip
  the GPU and cause SurfaceFlinger to fail.
- RADV GFX9 linear YUV planes require 256-byte pitch alignment; keep the minigbm
  alignment and regression tests.
- Meson uses `meson.options`; use `--wrap-mode=nofallback` to avoid its bundled Expat.
- Publish only changed build outputs; otherwise skipped Meson install targets can still
  rewrite timestamps.

## Actions
- [ ] Diagnose the camera — done when current boot logs establish whether the USB camera
  is enumerated and which camera/JPEG path fails.
- [ ] Confirm laptop rendering — done when current SurfaceFlinger or HWUI logs identify
  the active renderer.

### Ideas (not approved)
- Accelerated QEMU rendering; compare virgl/Venus options before implementation.
