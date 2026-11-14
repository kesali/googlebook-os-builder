# ANV (Intel Vulkan) in the pinned Android image

**Question:** Should this repo build ANV next to `amd` and `intel_hasvk`, or use the HAL
already supplied by Google's pinned image?

Researched 2026-11-14 against Mesa tag `mesa-26.3.0`, AOSP docs and the pinned Google Ruby
image. A trial source build succeeded; the final recipe keeps Google's existing ANV HAL
unchanged. No runtime or physical-device test was run.
`M/` = `https://gitlab.freedesktop.org/mesa/mesa/-/raw/mesa-26.3.0/`. Line numbers are as fetched and may drift.
Repo files cited are local paths.

## Finding
Mesa's ANV builds successfully, but the pinned Google Ruby vendor image already contains
`/lib64/hw/vulkan.intel.so`; its ELF symbols identify Mesa ANV and its SONAME matches that
HAL name. Keep this platform-matched binary unchanged and build HasVK separately for
Broadwell. A custom ANV build would collide with the existing path and its
`libvulkan_intel.so` SONAME does not match `vulkan.intel.so`. The final image rebuild passed
and retained the original ANV hash; runtime and physical-device behavior remain unverified.

The inspected input was `out/google/super/vendor_a.img` (SHA-256
`cfa3c4f99b7218f2a205c0d732d87df4694a7726817dd02b2462572ce87e468d`); the embedded HAL
SHA-256 is `5c687450523ea9ed9e8d4d9cc98ef4fef6c8d592d46db4bf425ad571dc6f7c73`.

## Pinned version
- `sources.mk:64-66` pins `MESA_VERSION := 26.3.0`. The tag `mesa-26.3.0` exists and its `meson.options` could be fetched.
- `scripts/mesa.sh:84` currently passes `-Dgallium-drivers=softpipe,zink,iris -Dvulkan-drivers=amd,intel_hasvk`.
- The same line also passes `-Dandroid-strict=false`, `-Dmesa-clc=system`, `-Dllvm=disabled`, `-Dplatforms=android -Dandroid-stub=true`.
- `tests/test_mesa.py:19` and `hardware/drivers/amdgpu/tests/test_mesa.py:16` assert the exact string `-Dvulkan-drivers=amd,intel_hasvk`. They would need to change with the flag.

## Meson option
- `vulkan-drivers` is an array option. Choices include `amd`, `intel`, `intel_hasvk`, `nouveau`, `swrast`, `all` (`M/meson.options:192-201`).
- **ANV is `intel`**. `intel_hasvk` is a separate choice. Mesa's own `auto` list for x86 is `amd, intel, intel_hasvk, nouveau, swrast` (`M/meson.build:274`). So the two coexist upstream.
- The change would be `-Dvulkan-drivers=amd,intel,intel_hasvk`.
- `meson.build:302-303` sets `with_intel_vk = contains('intel')` and `with_intel_hasvk = contains('intel_hasvk')` independently.
- `-Dintel-elk` defaults to true and is required by hasvk (`M/meson.options:716-722`, `M/src/intel/meson.build:6-12`). It is already satisfied by the current hasvk build.
- `-Dintel-rt` is a feature option, `auto` by default, and is disabled for non-ANV builds. ANV enables it on 64-bit (`M/meson.build:386-390`). Whether it adds a dependency on this build is unverified.
- Output library: `libvulkan_intel.so` (`M/src/intel/vulkan/meson.build:308`, `:53`). hasvk's is `libvulkan_intel_hasvk.so` (`M/src/intel/vulkan_hasvk/meson.build:19`). This matches the names already used in `scripts/mesa.sh:97`.

## Hardware generations, i915 and Xe
- ANV accepts Gfx9 and newer only. For older parts it returns `VK_ERROR_INCOMPATIBLE_DRIVER` with the comment "hasvk should pick up this device" (`M/src/intel/vulkan/anv_physical_device.c:3053-3057`).
- It rejects devices above Gfx30 unless `INTEL_FORCE_PROBE` is set (`anv_physical_device.c:3058-3064`).
- So **Broadwell (Gfx8), the repo's current Intel target, stays on hasvk**. ANV is relevant only to Skylake (Gfx9) and newer.
- ANV has both kernel backends: `i915/*` and `xe/*` sources are in `M/src/intel/vulkan/meson.build:169-189`. KMD type is chosen per device (`anv_physical_device.c:2520,2643`).
- Non-render engines are exposed only on Xe (`anv_physical_device.c:2886-2893`).
- Repo context, not Mesa: `docs/specs/graphics.md:12-18` says Google's Xe module is shipped and Xe binding is untested. Newer-Intel ANV would therefore also be untested.

## Android HAL name and install
- Android loader path: `/vendor/lib64/hw/vulkan.<ro.hardware.vulkan>.so`, with `ro.board.platform` as a fallback. Only one driver is supported. Source: https://source.android.com/docs/core/graphics/implement-vulkan ("Driver enumeration and loading").
- Mesa's Android doc says the loader wants the SONAME to match the file name, and shows `patchelf --set-soname vulkan.<name>.so` (`M/docs/android.rst:119-130`). It also lists the SELinux label `same_process_hal_file` (`M/docs/android.rst:425`).
- Existing convention: `hardware/drivers/i915/vendor.install:2` maps `lib64/hw/vulkan.intel_hasvk.so` to `mesa/lib64/libvulkan_intel_hasvk.so`. `hardware/drivers/i915/system_ext/graphics-intel-hasvk.rc` sets `ro.hardware.vulkan intel_hasvk`.
- Google's existing `lib64/hw/vulkan.intel.so` already matches `ro.hardware.vulkan=intel`; do not add another install entry.
- Because the loader supports only one driver, HasVK and ANV cannot both be loaded at once. `ro.hardware.vulkan` must select one per profile. The runtime selector now chooses the Broadwell-specific HasVK profile or ANV for other i915/Xe devices (see `docs/research/android-init-graphics-selection.md`); that selection has not been boot-tested.
- The final image's Google ANV has SONAME `vulkan.intel.so`, matching its HAL path. Mesa HasVK has SONAME `libvulkan_intel_hasvk.so` but is installed as `vulkan.intel_hasvk.so`; loader acceptance remains unverified. The Android documentation recommends matching SONAMEs, so this needs a runtime check.

## Android-specific behaviour and compatibility with current flags
- **`android-strict`:** with `-Dandroid-strict=false` (already set), `ANV_API_VERSION` is Vulkan 1.4 (`M/src/intel/vulkan/anv_api_version.h:14-24`). With strict, it is capped by `platform-sdk-version`: 1.1 below 33, 1.3 at 33+, 1.4 at 37+. With `platform-sdk-version=35` strict would give 1.3. `android-strict=false` is applied to all Vulkan drivers in the build and may cause CTS failures (`M/meson.options:38-45`).
- **Queues:** on Android, ANV forces `gc_count = 2` for HWUI, which wants at least two queues (`anv_physical_device.c:2820-2823`). This differs from the repo's RADV note that HWUI Vulkan is not used because RADV exposes one queue (`docs/specs/graphics.md:19-21`).
- **Gralloc / AHB:** ANV exposes `ANDROID_native_buffer` and `ANDROID_external_memory_android_hardware_buffer` only when `vk_android_get_ugralloc() != NULL` (`anv_physical_device.c:660-663`). It uses Mesa's u_gralloc, so it relies on the gralloc mapper that Mesa finds at runtime. This is not checked against this image's minigbm gralloc (`vendor.install:8`).
- **Local hasvk patch:** `hardware/drivers/i915/mesa-hasvk-ahb-format-query.patch` touches only `src/intel/vulkan_hasvk/anv_formats.c` (lines 8-9, hunk at 1525). It is independent of ANV, so no conflict is expected. ANV's AHB format query goes through common `vk_android_get_ahb_image_properties` (`M/src/intel/vulkan/anv_formats.c:2163-2170`). This matches the premise in `docs/patch-audit.md:20`. Whether ANV hits the same optional-struct gate was not exercised.
- **Build host tools:** ANV compiles internal shaders using `prog_mesa_clc` (`M/src/intel/shaders/meson.build:30-48`) for Gfx8 to Gfx35. The repo already passes `-Dmesa-clc=system` with host `mesa_clc` and `vtn_bindgen2` from `scripts/mesa-clc.sh:10-34`. `meson.build:1032-1034` requires both with `system`. Whether that host build covers ANV's inputs (e.g. `precomp-compiler`, `-Dintel-rt`) is unverified.
- **LLVM:** `-Dllvm=disabled` is already used. ANV does not appear to need LLVM when `mesa-clc` is system, but a configure run is needed to confirm.
- **Dependencies:** libdrm is required (`M/src/intel/vulkan/meson.build:255`). The build already builds libdrm into the sysroot (`scripts/mesa.sh`). Intel libdrm support (`dep_libdrm_intel`, `M/meson.build:772-777`) was not checked against the current libdrm options.
- The source-built experiment produced `libvulkan_intel.so` with SONAME `libvulkan_intel.so`; it is not included in the final image.

## Unresolved
1. Whether any target machine has Gfx9+ Intel. The repo's only Intel profile is Broadwell, and no Gfx9+ hardware or profile was found.
2. Runtime selection between HasVK and ANV per GPU, and whether init selects after DRM binding. Android loads only one Vulkan driver.
3. Google's prebuilt identifies as Mesa 26.1.3 (`git-a386f8e15a`), versus this repo's
   Mesa 26.3.0 pin; its exact source revision, patches, and supported-device range are unknown
   (see [Google driver packaging](./google-android-graphics-driver-packaging.md)).
4. Xe or i915 behaviour on Gfx9+ with the shipped GKI modules.
5. ANV + Google camera/HWUI behaviour and gralloc compatibility on this image.

## Sources
- Mesa 26.3.0 tag: `M/meson.options`, `M/meson.build`, `M/docs/android.rst`, `M/src/intel/meson.build`, `M/src/intel/vulkan/{meson.build,anv_physical_device.c,anv_formats.c,anv_api_version.h}`, `M/src/intel/vulkan_hasvk/meson.build`, `M/src/intel/shaders/meson.build`.
- Android Vulkan implementation: https://source.android.com/docs/core/graphics/implement-vulkan

## Follow-up: kernel-reported Intel graphics version without a PCI-ID table
Researched 2026-11-14 against the pinned kernel tag `android17-6.18-2026-06_r52` (`sources.mk:15`; its `Makefile` reports 6.18.21).
`K/` = `https://android.googlesource.com/kernel/common/+/refs/tags/android17-6.18-2026-06_r52/`. Files were read through gitiles with `?format=TEXT`; no kernel was built or booted.

**Answer: no stable sysfs attribute exists in either driver.** The only kernel-exported graphics-version values found are in debugfs, which is neither stable ABI nor normally available to Android userspace.

- **i915, sysfs:** `K/drivers/gpu/drm/i915/i915_sysfs.c` creates only the `l3_parity` and `l3_parity_slice_1` binary files (lines 140-171). The engine sysfs (`K/drivers/gpu/drm/i915/gt/sysfs_engines.c`) exposes `name`, `class`, `instance`, `mmio_base` and scheduling tunables. No IP version attribute.
- **Xe, sysfs:** `K/drivers/gpu/drm/xe/xe_device_sysfs.c:272-302` adds only the `vram_d3cold_threshold` group (when d3cold-capable) and, for Battlemage only, the link-downgrade and late-bind groups. The GT kobject code (`xe_gt_sysfs.c`) adds no version attribute either. No IP version attribute.
- **i915, debugfs only:** `i915_capabilities` (`K/drivers/gpu/drm/i915/i915_debugfs.c:65-75,704`) calls `intel_device_info_print`. That prints `graphics version: <ver>` or `<ver>.<rel>` and `media version:` (`K/drivers/gpu/drm/i915/intel_device_info.c:93-107`). It is the ordinary 8, 9, … number, for example `graphics version: 8` for Broadwell. I did not confirm that Broadwell's table entry has ver 8; this is inferred from the shared hasvk/ANV split at Gfx9 in the Mesa section above.
- **Xe, debugfs only:** the `info` file (`K/drivers/gpu/drm/xe/xe_debugfs.c:64-90,185`) prints `graphics_verx100 <n>` (for example 1200), `media_verx100`, `devid 0x…`, `platform`. The parent directory is the DRM minor's debugfs directory, normally `/sys/kernel/debug/dri/<minor>/`. The exact directory layout was not checked.
- Format differs between the drivers (`graphics version: 9` versus `graphics_verx100 1200`), and neither is documented as ABI. Reading them also needs `CONFIG_DEBUG_FS`, a mounted debugfs and root. Whether this image's Android kernel config and SELinux policy allow init to read it was not checked.
- **Xe never needs hasvk:** Xe's pre-GMD-ID tables start at `Xe_LP` (verx100 1200) (`K/drivers/gpu/drm/xe/xe_pci.c:136-139,168`). I did not exhaustively check the supported platform list, so "Xe is Gfx12+ only" is from the table's earliest entry. Gfx8 can only be bound by i915.
- **Upstream consumers:** ANV derives the generation itself in userspace via `intel_get_device_info_from_fd` and returns `VK_ERROR_INCOMPATIBLE_DRIVER` for ver < 9 (`M/src/intel/vulkan/anv_physical_device.c:3053-3057`). I did not trace how Mesa maps device IDs for each kernel driver, but the function name and the failure path indicate it is a userspace table keyed on the device. I found no kernel sysfs path used for this.

### Options for the selector, and caveats
1. **Use the driver name as the first split.** If the bound driver is `xe`, choose ANV; no table needed. If `i915`, a generation is still required. This relies on the previous point about Xe.
2. **For i915, read debugfs `i915_capabilities`** and parse `graphics version`. This is the only in-kernel source found. It is debug interface and may change; it also needs debugfs access (above).
3. **Keep a PCI-ID match** (what the repo does today for AMD and Intel in `boot/android-menu.cfg:28-37`) if debugfs is unavailable.
4. **Run a userspace probe that uses Mesa's own detection.** Mesa has a developer tool for this, but I did not verify its name, build option or Android availability. Alternatively let the loader try ANV and fall back; Android loads only one HAL, so this cannot be done by the loader.
- Not verified: other kernel uAPI. I did not search `i915_drm.h` or `xe_drm.h` for a graphics-version query, so I cannot say none exists.
- Not verified: i915 prints these on a Gfx8 device on this kernel; no hardware test was done.
- Timing: whether debugfs is mounted and the DRM device bound before the init stage that selects the profile is unknown (see `docs/research/android-init-graphics-selection.md`).
