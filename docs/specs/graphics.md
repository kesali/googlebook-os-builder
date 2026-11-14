# Graphics

**Status:** partial — the QEMU selector sets softpipe with SELinux enforcing and reaches
the Android welcome screen; native graphics on physical devices remain unverified.
**Last verified:** 2026-11-14 — `make test` (326 tests), `make android-image` and
`make qemu-check` pass; the packed policy contains the selector's property-set rule.

## Goal
Provide a software fallback and best-effort native graphics across more x86-64-v3 laptops,
keeping model-specific behavior separate from GPU-family selection.

## Current state
The pinned Google vendor image includes the ANV HAL at `lib64/hw/vulkan.intel.so`; keep it
unchanged. The Mesa 26.3.0 build provides RADV/Zink, Broadwell HasVK and softpipe. A
post-fs-data selector maps bound amdgpu to RADV/Zink, i915/Xe to Google's ANV, and known
Intel PCI ID `8086:1616` to Mesa HasVK; unknown drivers use softpipe. It prefers the GPU
marked `boot_vga`.
The pinned drivers expose no stable graphics-generation sysfs attribute, so other i915 devices
try ANV even if they predate its Gfx9 support. Device quirks now use a separate boot property,
though GRUB still identifies the two known models by their existing GPU IDs. The image build
preserved Google's ANV HAL byte-for-byte and installed Mesa HasVK. The selector now sets
`sys.gbos_builder.graphics=softpipe` in QEMU; the service exits successfully and the softpipe
profile starts. HasVK's ELF SONAME is `libvulkan_intel_hasvk.so`, while its HAL filename is
`vulkan.intel_hasvk.so`; loader acceptance, physical-device selector timing and binding,
multi-GPU behavior, and graphics on other physical devices remain unverified.

The owner reports the MSI graphics work on the existing image; the active SurfaceFlinger/HWUI
renderer was not supplied. The camera is not detected and shows a black screen; its cause and
a software camera fallback are unknown. The Lenovo profile has not been retested on the
current image. The generic i915 module-load alias passed GKI and image checks. Google's Xe
module remains included; binding and display on another device remain untested.

## Decisions
- Keep softpipe as the verified QEMU fallback. Build Mesa without LLVM; RADV uses ACO.
- Use experimental runtime driver-family selection. Keep the known Broadwell HasVK profile
  for `8086:1616`; unclassified i915/Xe devices try ANV. Unknown drivers use softpipe.
- Keep device quirks on a separate property. GRUB still maps the known MSI/Lenovo GPU IDs
  to their device profiles; replacing those proxies with verified model identification remains
  future work.
- Keep Intel HWUI and RenderEngine on GL until ANV and gralloc are tested. Keep GL HWUI for
  AMD and RADV for its Vulkan RenderEngine.
- Use upstream `android-strict=false` for native RADV/ANV/HasVK capabilities. This affects
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
- [android/system_ext/graphics-select.sh](../../android/system_ext/graphics-select.sh) —
  early runtime driver-family selection.
- [hardware/drivers/i915/system_ext/graphics-intel-anv.rc](../../hardware/drivers/i915/system_ext/graphics-intel-anv.rc)
  and [hardware/drivers/i915/system_ext/graphics-intel-hasvk.rc](../../hardware/drivers/i915/system_ext/graphics-intel-hasvk.rc) —
  Intel Vulkan profiles.
- [hardware/drivers/amdgpu/system_ext/graphics-amd.rc](../../hardware/drivers/amdgpu/system_ext/graphics-amd.rc) —
  shared AMD profile; [hardware/msi-modern-15-b7m/system_ext/display-msi.rc](../../hardware/msi-modern-15-b7m/system_ext/display-msi.rc)
  retains the MSI panel quirk.
- [docs/research/mesa-anv-android-feasibility.md](../research/mesa-anv-android-feasibility.md) —
  upstream ANV build findings and remaining limits.

## Verify
Run `make test`, `make android-image` and `make qemu-check`; inspect the screenshot and
confirm softpipe. This does not prove native GPU or camera behavior. On hardware, check the
selected profile, native display, and SurfaceFlinger/HWUI renderer logs.

## Pitfalls
- Missing labels on GPU `uevent`, vendor, device or subsystem files can make libdrm skip
  the GPU and cause SurfaceFlinger to fail.
- RADV GFX9 linear YUV planes require 256-byte pitch alignment; keep the minigbm
  alignment and regression tests.
- Meson uses `meson.options`; use `--wrap-mode=nofallback` to avoid its bundled Expat.
- Publish only changed build outputs; otherwise skipped Meson install targets can still
  rewrite timestamps.

## Actions
- [ ] Verify Intel Vulkan HAL loading — done when ANV works on Gfx9+ and HasVK works on
  Broadwell without loader errors.
- [ ] Verify generic i915 display — done when a physical result is reported separately
  from the software-rendering fallback, including the selected runtime profile.
- [ ] Diagnose the camera — done when current boot logs establish whether the USB camera
  is enumerated and which camera/JPEG path fails.
- [ ] Confirm laptop rendering — done when current SurfaceFlinger or HWUI logs identify
  the active renderer.

### Ideas (not approved)
- Accelerated QEMU rendering; compare virgl/Venus options before implementation.
