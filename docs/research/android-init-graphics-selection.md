# Android init graphics selection

**Question:** Can Android select a graphics profile from the bound DRM driver
before the graphics stack starts, without changing the pinned kernel?

## Finding

The Android 17 init sequence makes this feasible in principle, but the current
profile import cannot be selected by a property discovered later at runtime.
A selector would need to finish before `zygote-start` because the current
profiles set display properties read by Zygote, and before `boot` starts the
composer and SurfaceFlinger services. The Ruby image's actual DRM binding time
at those triggers remains unverified.

## Relevant ordering

- `androidboot.*` command-line values become `ro.boot.*` before init parses rc
  files. See AOSP
  [property initialization](https://android.googlesource.com/platform/system/core/+/refs/tags/android-17.0.0_r1/init/property_service.cpp#L1386)
  and [second-stage init](https://android.googlesource.com/platform/system/core/+/refs/tags/android-17.0.0_r1/init/init.cpp#L1126).
- Init expands a property in an `import` path while parsing it. A later
  runtime property change does not cause that import to be reevaluated.
  See AOSP [import parsing](https://android.googlesource.com/platform/system/core/+/refs/tags/android-17.0.0_r1/init/import_parser.cpp#L26)
  and [boot script loading](https://android.googlesource.com/platform/system/core/+/refs/tags/android-17.0.0_r1/init/init.cpp#L347).
- First-stage init loads modules listed in its ramdisk before second-stage init.
  Later uevent-based module loading can occur during coldboot; Android waits
  for coldboot before the `init` trigger. See AOSP
  [first-stage init](https://android.googlesource.com/platform/system/core/+/refs/tags/android-17.0.0_r1/init/first_stage_init.cpp#L218)
  and [init action ordering](https://android.googlesource.com/platform/system/core/+/refs/tags/android-17.0.0_r1/init/init.cpp#L1238).
- The `late-init` sequence reaches `post-fs-data`, then `zygote-start`, then
  `early-boot` and `boot`. The image's HWC service is `class hal animation`;
  `on boot` starts `hal` before `core`, where SurfaceFlinger is
  `class core animation`. See AOSP
  [late-init actions](https://android.googlesource.com/platform/system/core/+/refs/tags/android-17.0.0_r1/rootdir/init.rc#L518)
  and [boot service startup](https://android.googlesource.com/platform/system/core/+/refs/tags/android-17.0.0_r1/rootdir/init.rc#L1219),
  plus the [SurfaceFlinger service](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-17.0.0_r1/services/surfaceflinger/surfaceflinger.rc#L1).

## Implication for this image

- [The GRUB menu](../../boot/android-menu.cfg) supplies the graphics value
  through the kernel command line. [The shared init file](../../android/system_ext/gbos-builder.rc)
  uses it in an `import` path, so this path is static at rc-parse time.
- A runtime detector cannot simply set a value and expect that import to load a
  different file. The current prototype statically imports profile actions and
  has a one-shot selector set a separate writable property at `post-fs-data`.
- The selector must also finish before `zygote-start`; `early-boot` is too late
  for the density settings currently read by Zygote. The local HWC service is
  later, at `boot`, but another early graphics HAL could impose an earlier
  deadline.
- The local image's GPU modules are not in the boot ramdisk's `modules.load`.
  The vendor init scripts start module-loading services during `early-init` and
  `init`. The module script documents uevent alias loading when enabled, but
  whether this image enables it and when a GPU driver binds are unverified.
  Source ordering alone does not prove a DRM driver has bound by `post-fs-data`.

## Must verify in the image and on hardware

- In an enforcing boot, whether `i915`, `xe`, or `amdgpu` is bound and visible
  under `/sys/class/drm` before `post-fs-data` completes.
- Whether a selector can read the relevant sysfs entries and set its property
  under the image's SELinux policy, with softpipe fallback.
- Whether the selector and profile actions run before Zygote reads density and
  before any graphics HAL starts; confirm from init logs, not just source order.
-   Separate graphics-backend selection from device identity. The prototype now
  uses a separate boot property for the MSI and Lenovo audio/display quirks, but
  GRUB still identifies those known device profiles by GPU ID.

  ## Prototype update

  The selector at [graphics-select.sh](../../android/system_ext/graphics-select.sh)
  maps amdgpu to AMD, Xe/i915 to Intel ANV except known Broadwell `8086:1616` to
  HasVK, and unknown drivers to softpipe. Its init service starts at
  `post-fs-data`, before `zygote-start`. The pinned kernel exposes no stable
  graphics-generation sysfs attribute, so other pre-Gfx9 i915 devices may select
  ANV even though it cannot support them. The implementation and Mesa build
  change have focused tests only; no image build or runtime boot has verified
  driver binding, SELinux access, or graphics output.

  The AOSP tag is a reference; the Ruby image may carry vendor changes to init
  and service configuration.
