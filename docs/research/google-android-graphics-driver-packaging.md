# How Google's Android image packages graphics drivers

Researched 2026-11-14 against AOSP graphics documentation, Mesa source, and the pinned
Google Ruby vendor image. Local image evidence is read-only from
`out/google/super/vendor_a.img` (SHA-256
`cfa3c4f99b7218f2a205c0d732d87df4694a7726817dd02b2462572ce87e468d`).

## Short answer

The image contains Mesa's Intel ANV Vulkan driver, not a different Intel Vulkan
implementation. The binary identifies itself as Mesa 26.1.3 (`git-a386f8e15a`) and
contains paths under `vendor/google/graphics/desktop/mesa3d/intel`. That points to a
Google Android vendor source tree, but the exact source revision, build system, and Google
patches are not publicly established from the image alone.

Android graphics support is layered: the kernel needs a compatible DRM driver, while the
vendor image supplies the user-space Vulkan driver and the buffer/display HALs it works
with. A binary in the image does not by itself make every GPU compatible.

## What the pinned vendor image contains

| Image evidence | What it indicates |
|---|---|
| `/vendor/lib64/hw/vulkan.intel.so`, SONAME `vulkan.intel.so` | Mesa ANV exposed as Android's Intel Vulkan HAL. SHA-256: `5c687450523ea9ed9e8d4d9cc98ef4fef6c8d592d46db4bf425ad571dc6f7c73`; build ID: `dc904b0a4f55db2581e5aa181e688a236f77aaa9`. |
| Vendor build properties `ro.hardware.vulkan=intel`, `ro.hardware.egl=angle` | Selects the Intel Vulkan HAL; EGL/GLES is configured for ANGLE. |
| `libdrm.so`, `libigdgmm_android.so` | User-space DRM and Intel memory-management dependencies. |
| `gralloc.minigbm.so`, `mapper.minigbm.so`, minigbm allocator, DRM composer | Buffer allocation, mapping, and display composition. These are separate from ANV itself. |

The ANV binary exports Mesa `anv_*`, `intel_*`, `nir_*`, and Vulkan symbols. Its embedded
version is 26.1.3, while this repository's Mesa source pin is 26.3.0. I found no Mesa
EGL/GLES or Iris library in the vendor partition's `/lib64` paths; that does not rule out
libraries elsewhere in the system image.

## How Android loads it

AOSP describes the Vulkan loader as a system library that discovers a vendor driver through
the HAL mechanism. Its preferred 64-bit path is
`/vendor/lib64/hw/vulkan.<ro.hardware.vulkan>.so`; only one driver is loaded at a time,
although it may support multiple physical devices. Thus `ro.hardware.vulkan=intel` selects
`vulkan.intel.so`. See [AOSP Vulkan implementation and driver loading](https://source.android.com/docs/core/graphics/implement-vulkan).

Other pieces are separate HALs. AOSP documents gralloc as a vendor-specific allocator and
the Hardware Composer HAL as the display-composition interface; see
[AOSP graphics architecture](https://source.android.com/docs/core/graphics/architecture).
The image's minigbm and DRM composer therefore explain how buffers reach the display, not
how ANV implements Vulkan.

## What is and is not known about Google's Mesa

- The ANV binary's version string is `26.1.3 (git-a386f8e15a)`. The public Mesa 26.1.3
  release tag has a different commit, so the binary does not establish an exact upstream
  source revision.
- Embedded build paths include `vendor/google/graphics/desktop/mesa3d/intel/...`, and
  strings identify the ANV implementation. This is strong evidence of a Google Android
  vendor build of Mesa, but does not reveal the build system or source changes.
- The label `android_vendor_x86_64_pantherlake` appears in generated-source strings. It is
  a build-variant name, not proof that the driver supports only Panther Lake.
- Google's source tree and patch set were not available for comparison. It is not possible
  to say which changes are Google-specific or whether they are patches, backports, or build
  configuration.

Upstream Mesa's [Android guide](https://gitlab.freedesktop.org/mesa/mesa/-/raw/mesa-26.1.3/docs/android.rst)
describes Android HAL naming and packaging. Mesa's
[ANV Android implementation](https://gitlab.freedesktop.org/mesa/mesa/-/raw/mesa-26.1.3/src/intel/vulkan/anv_android.c)
and [Vulkan Android runtime](https://gitlab.freedesktop.org/mesa/mesa/-/raw/mesa-26.1.3/src/vulkan/runtime/vk_android.c)
contain the corresponding driver and HAL code.

## Implication for this repository

Keep Google's `vulkan.intel.so` unchanged instead of installing a duplicate ANV. Build
HasVK separately for the known Broadwell case. Broader support still needs a compatible
kernel DRM driver, correct HAL selection, and tested buffer/display integration. The image
does not prove that our experimental selector works on hardware.

Unverified: ANV runtime behavior on this image, the exact Google source revision and patches,
the supported GPU generations of this specific prebuilt, and the selector's timing relative
to kernel driver binding.
