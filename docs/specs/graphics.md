# Graphics

**Status:** partial — QEMU softpipe works; the laptop desktop and camera work, and Chrome uses RADV.
**Last verified:** 2026-11-04 — HttpEngine crypto candidate: 29 tests, exact ABI, image metadata,
no-write repeat and enforcing QEMU/native checks pass; subsequent Lenovo test owner-accepted.
Dedicated HttpEngine requests and MSI regression remain unverified.
[Evidence](../../out/httpengine-investigation/).

Earlier, 2026-11-04 — Recipe refactor: 263 tests, exact patch/profile/input equality,
image metadata and 38-output byte equality pass; 23.8 s no-write repeat preserves timestamps.
Direct and USB-UEFI softpipe setup screens inspected under enforcing SELinux; direct tap opens
inspected Accessibility. Physical AMD/Intel regression remains. [Evidence](../../out/full-hardware-recipes/).

Earlier, 2026-11-03 — Lenovo logs prove i915/Iris enumeration but desktop presentation
fails (fb -22). Churro's primary-alpha candidate passes 33 tests, kernel/image/metadata checks,
no-write repeat and disposable enforcing QEMU setup/input (screens inspected); hardware retest
pending. [Evidence](../../out/intel-primary-alpha/). Owner confirms the pre-patch MSI image boots.
Subsequent owner test: guest and another profile reach desktop, performance feels good and
video plays. [Successful boot logs](../../out/laptop-logs/20261103-185854-21kebgv7/current/)
show no framebuffer rejection. Original-profile freeze with flashing Caps Lock remains
unexplained; recovered logs contain no panic trace. Hardware video decoding is not established.

Earlier, 2026-11-03 — Fresh expanded image builds; 92 focused tests and enforcing
direct/UEFI QEMU setup/input checks pass. Iris/softpipe/Zink compile without shipping LLVM.
Hardware was not yet tested at that point. [Evidence](../../out/intel-bringup/fresh/).
Earlier, 2026-11-02: the owner reports working camera preview and recording
([logs](../../out/laptop-logs/20261102-231851-2bm_5yev/current/)). Earlier,
`make test` (113 tests), `make mesa JOBS=12`,
`make android-image JOBS=12` and `make qemu-check JOBS=12` pass; the inspected QEMU screenshot
shows the setup screen. The owner completed setup on the laptop and finds apps and graphics fast.
That boot's log ([android.log](../../out/laptop-boot-2026-11-02-hdmi/current/)) shows Chrome's
ANGLE on `Vulkan 1.1.363 (AMD Radeon Graphics (RADV RENOIR) (0x000015E7))`; SurfaceFlinger and
HWUI do not log their renderer. The owner subsequently tested the Vulkan HWUI entry with no
noticeable performance difference and reported HDMI performance is now fine.
Earlier,
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
Verified: graphics source patches/header now belong to DRM handoff/amdgpu recipes;
Intel and QEMU profiles belong to their driver recipes. AMD profiles stay MSI-owned because
they include the owner's panel density. Asset/patch bytes and ordering match the baseline;
build, ABI, image equality and softpipe QEMU checks pass above. No new physical GPU test.

Lenovo hardware attempt (2026-11-03): [saved boot](../../out/laptop-logs/20261103-181307-7gwlz7mk/current/boot.txt)
selects Intel; i915 binds and EGL reports `Mesa Intel(R) HD Graphics 5500 (BDW GT2)`,
OpenGL ES 3.2. After animation the display goes dark while keyboard activity wakes backlight.
drmhwc logs framebuffer creation -22, failed AtomicCommitArgs and BAD_DISPLAY; no rejected
format is printed. Churro documents the same Broadwell failure with alpha client targets.
The approved [kernel candidate](../../hardware/drivers/i915/i915-gen4-primary-alpha.patch) reuses its fix;
local validation passes; subsequent desktop/video results are recorded above.
Bluetooth initialization crashes are separate.
Owner confirms the expanded image boots MSI; wider regression has not been reported.

Broadwell integration (2026-11-03, enumeration verified above): unchanged upstream Iris builds into
Mesa alongside softpipe/Zink; native `mesa_clc`/`vtn_bindgen2` use builder-only LLVM 19.
The [Intel profile](../../hardware/drivers/i915/system_ext/graphics-intel.rc) renders with Iris GLES
without software forcing or AMD overrides; GRUB selects it only for the Lenovo's `8086:1616` GPU.
Since 2026-11-04 (owner-confirmed on the Lenovo) it also offers Mesa hasvk Vulkan 1.3 to apps
for Google's camera HAL; SurfaceFlinger and HWUI stay on GL. Chrome's ANGLE also picks hasvk;
its pages stayed grey because hasvk rejects the Android-hardware-buffer format query unless the
optional `VkExternalImageFormatProperties` is chained (Mesa main too), so every shared image failed.
[mesa-hasvk-ahb-format-query.patch](../../hardware/drivers/i915/mesa-hasvk-ahb-format-query.patch)
accepts it as anv and RADV do; an upstream candidate. Gralloc never picks CCS on gen8.
Signed i915/intel-gtt reuse Google's helpers; only that i915 alias is installed.
The separate enlarged-layout vendor image is 354,205,696 B within its 387,108,864 B limit.
All 1,622 vendor and 237 system_ext entries pass metadata/import checks; 69 focused tests pass.
Repeat Mesa builds preserve published bytes/timestamps. Shared EGL/Gallium/GBM backend and RADV
bytes changed; GLES entry libraries, Mesa GBM core and RadeonSI VA/helper remain identical.
Direct-kernel and USB/UEFI QEMU reach inspected setup screens with stable services and enforcing
SELinux; an injected tap opens accessibility (screens inspected), and the NVMe decoy stays
unchanged. [Evidence](../../out/intel-bringup/).
The subsequent owner-approved fresh expanded image now builds through the normal pipeline:
vendor_dlkm has 64 MiB and logical B is removed, without changing the old local disk or USB.
See [image spec](os-image.md). Lenovo i915/Iris binding and subsequent desktop/video are
confirmed as described above; MSI boots by owner report, not a full peripheral regression.
No Intel Vulkan, audio or network support is claimed.

Verified: source-built Mesa and minigbm work with Google's unchanged composer, allocator service
and mapper on virtio-gpu. RADV/Zink and the AMD allocator backend build; all 49 gralloc and 22 GBM
exports used by Google's clients are present. The prior laptop kernel loaded amdgpu as DRM minor 1,
but SurfaceFlinger repeatedly reported invalid present fences. The
[source-level handoff](../../hardware/drivers/drm-handoff/drm-firmware-handoff.patch) gives virtio card0 in QEMU and a
visible setup screen on the laptop. On the laptop, Chrome renders through ANGLE on RADV; which
renderer SurfaceFlinger and HWUI use, and the frame rate, are not measured. The opt-in RADV
two-queue Vulkan HWUI candidate was tested by the owner with no noticeable performance difference;
the default AMD profile remains GL. QEMU is still CPU-rendered.

The owner now confirms video playback is fixed after the source-level YV12 changes below.
The first
[logs](../../out/laptop-boot-2026-11-02-video/dali-bootlog/current/) show software AVC/HEVC/VP9
selection and 11 `media.swcodec` crashes: minijail blocks `sched_getaffinity` while Mesa maps a
video buffer through minigbm. The vendor policy extension below allows only this query.
Validation: 16 graphics/overlay tests pass; the image rebuild changed only vendor and the repeat
build wrote nothing. Enforcing QEMU reaches the inspected setup screen; explicit
`c2.android.avc.encoder` screen recording succeeds with `media.swcodec` still at `Seccomp: 2`,
and the guest can read the installed rule ([evidence](../../out/video-codec-runtime/)).
After installing it, the owner reports that video crashes the desktop. The owner previously fixed
the same symptom in gbos: YV12 format reporting and chroma-plane pitch
([reference handoff](../../reference/gbos-x86-msi-modern-15-B7M/HANDOFF.md)).
The pinned sources still contain both gaps: RADV reports no external format for YV12, and the
allocator's planar fallback does not align chroma pitches for GFX9. Source patches now reuse
Mesa's common gralloc-aware format query and align planar luma to 512 bytes (chroma to 256).
RADV's 32-bit memory exclusion, directly supported RGB/NV12 queries and software decoding remain.

Verified: `make test` passes 131 tests, including compiled query/error-path and pitch tests through
8K widths. Mesa/minigbm compile, all 49 gralloc and 22 GBM exports pass, vendor's 1,620 metadata
entries pass, and the repeat image build writes nothing. Enforcing QEMU reaches the inspected
setup screen ([build](../../out/video-yv12-build.log), [QEMU](../../out/video-yv12-qemu.log)).
Not verified independently: the original desktop crash's log signature (not retrieved) or
hardware playback measurements. QEMU's virtio allocator does not exercise the AMD video-buffer
path. The owner subsequently confirms the previously failing game, another native app and
Hearthstone work with Berberis; see [boot diagnostics](boot.md) for the translator comparison.
Houdini's internal failure cause is not established.

Camera VA-API candidate (built; laptop decoding unverified): the latest laptop
[capture logs](../../out/laptop-logs/20261102-212827-m7k5rziw/current/) show the USB camera HAL
aborting in `HardwareJpegDecoderVaapi` after libva cannot load `radeonsi_drv_video.so`.
The kernel already reports `jpeg_v2_0` and a `jpeg_dec` ring; Google's image supplies libva
1.22 and Intel iHD, but no AMD VA driver. Owner approved building upstream RadeonSI VA-API
in a separate JPEG-decode-only Mesa build, preserving Google's runtime and rendering defaults.
[sources.mk](../../sources.mk) pins libva 2.22.0 headers (VA-API 1.22); upstream Meson generates
the version header, but no replacement libva library is built or installed.
The rendering codec defaults stay unchanged; the VA build enables only JPEG decoding.
LLVM stays disabled, and publication
requires the VA 1.22 entry point. Tests cover publication/no-write behavior and missing exports.
The combined build required libelf for unrelated RadeonSI graphics code; upstream's
decode-only configuration avoids it without a patch. Static linking then collided on unrelated
Mesa/libdrm `handle_table_remove` functions. The owner approved a separate shared DRM build:
ship only `libdrm_amdgpu.so`, using Google's unchanged `libdrm.so`. Both upstream Android
SONAMEs are unversioned (unlike the host Linux helper); rendering still links DRM statically.

Verified: 20 focused tests pass, including dependency-keyed VA configuration and no-write
publication. `make android-image JOBS=12` succeeds in 58.9 s; 1622 vendor metadata entries
pass and 349,450,240 B fits the 387,108,864 B limit. Installed bytes match both new libraries;
all 195 driver and 66 helper strong imports resolve against shipping libraries. Google's libva
and core libdrm, plus all seven rendering libraries, remain byte-identical to their baselines.
The 21.0 s repeat preserves 39 published sizes/timestamps and writes no partitions or boot files.
Bounded QEMU passes in 79.0 s with enforcing SELinux, stable services and softpipe; setup
screenshot inspected and VM exit confirmed. Input was not retested.
[Evidence](../../out/camera-vaapi/). At this build stage, camera-HAL namespace loading, AMD JPEG
profiles/decoding and preview/capture were not verified. QEMU has no AMD webcam decode path;
subsequent laptop retests are below.

Owner retest: preview is still black. Boot `e42498e7-47ba-451f-b88a-cf9eeb462511`
loads the VA entry point in the media capability probe, but driver initialization returns 2.
Camera crashes still name the JPEG decoder's `RESOLUTION_BOUND`; its detailed initialization
logs have rotated out ([logs](../../out/laptop-logs/20261102-221612-z03h9kht/current/)).
Source tracing found a likely configuration conflict: the AMD profile globally exports
`MESA_LOADER_DRIVER_OVERRIDE=zink`; the VA pipe loader honors it, but its build contains
only RadeonSI. Approved [camera-va-driver.patch](../../hardware/drivers/amdgpu/vendor/camera-va-driver.patch)
clears that variable only in the USB camera service, retaining automatic DRM detection,
desktop Zink and enforcing SELinux. 21 focused tests pass; the 28.6 s image rebuild reads
back the exact service edit and verifies 1622 metadata entries and partition fit. The 17.2 s
repeat preserves all 39 published sizes/timestamps and writes nothing. Bounded QEMU passes
in 77.7 s; setup screenshot inspected, enforcing SELinux, stable services, VM exit confirmed
(input not retested). [Evidence](../../out/camera-va-override/). Physical retest remains pending.
GPU-service/property denials are also present, but not proven causes of this abort.

Next owner retest (`dc40de8f-009e-4ef5-a671-9b5acb3af439`) confirms the camera service
initializes VA successfully (`va_openDriver() returns 0`); the JPEG initialization abort is
absent from retained crash evidence. Preview still fails: VC effects rejects
`VK_EXT_image_drm_format_modifier` because Vulkan 1.2 or `VK_KHR_image_format_list` is
required, while RADV reports 1.1 ([logs](../../out/laptop-logs/20261102-224045-sm_8d1oi/current/)).
The reference Churro HASVK patch documents the same camera dependency failure.
Owner approved upstream `-Dandroid-strict=false` for the rendering build rather than another
source patch: RADV exposes its native version/extensions. VA configuration, renderer selection
and SELinux stay unchanged. This affects all RADV clients, not only the camera.
Verified: 22 focused tests pass; the 114.2 s Mesa/image build succeeds with 1622 vendor
metadata entries and partition fit. Meson introspection and both RADV version-reporting
compile commands confirm strict mode is disabled; the VA build retains it. Installed RADV,
VA and AMD-helper bytes match publication; Google libva/libdrm and the camera service
override are preserved. The 17.7 s repeat preserves 39 published sizes/timestamps and writes
nothing. Bounded QEMU passes in 77.3 s (enforcing SELinux, stable services, softpipe);
setup screenshot inspected and VM exit confirmed; input not retested.
[Evidence](../../out/camera-vulkan/). Not verified: physical RADV version/extension enumeration,
desktop/app regression or camera preview/capture. QEMU softpipe cannot prove those.

Owner retest (`df0b9859-30cd-4454-8299-cd2bddbcff5b`): the activation indicator appears and
effects create a RADV Vulkan 1.4 context, but every frame fails AHWB import with
`ERROR_INVALID_DRM_FORMAT_MODIFIER_PLANE_LAYOUT_EXT`. The allocator's spoofed NV12 path aligns
width only to 32, suggesting a 640-byte pitch at 640x480; the actual AHWB plane layout was not
logged. RADV requires 256-byte linear pitches on GFX9.
[minigbm-yuv-pitch.patch](../../hardware/drivers/amdgpu/minigbm-yuv-pitch.patch)
(renamed from the YV12 patch) also aligns NV12/NV21 widths to 256. 19 focused tests, GBM wrapper
check, minigbm ABI gate, 30 s image build (only `vendor_a` written), 17 s no-write repeat and
enforcing QEMU (77 s, screen inspected, VM exited) pass. [Evidence](../../out/camera-pitch/).
The owner confirms camera preview and video recording work. In boot
`7e418353-cba2-48a6-8994-c7f60114b837`, VA initializes, the logs show 640x480 YUYV and 1280x720
MJPG sessions with none of the earlier import errors. The logs do not independently establish
which decoder processed the frames. The webcam LED also flashes under Linux; its cause is unknown.

## Decisions
- Expose native RADV and Broadwell hasvk Vulkan capabilities with upstream `android-strict=false`
  (no Churro version patch needed): Google's camera effects cannot initialize with the
  strict-mode 1.1 cap. This also removes Android extension
  allowlist filtering, so desktop/app rendering requires regression testing; no CTS claim.
- Owner's overnight request authorizes an AMD test candidate, retaining softpipe as the verified fallback.
- Mesa 26.3.0-rc3, libdrm 2.4.133, Expat 2.7.3 from source, NDK r30 at API 35;
  softpipe, Zink and RADV with ACO, no LLVM/GLX; the approved RadeonSI VA candidate adds
  hardware JPEG support without changing renderer selection. Rendering links libdrm, Expat and
  Mesa's C++ runtime statically to avoid vendor linker-namespace problems. Only the separate
  VA driver uses shared DRM, adding the AMD helper but preserving Google's core runtime.
  Pins: [sources.mk](../../sources.mk).
- Software rendering is selected with `LIBGL_ALWAYS_SOFTWARE`/`GALLIUM_DRIVER` in
  [graphics-softpipe.rc](../../hardware/drivers/qemu-virtio/system_ext/graphics-softpipe.rc), not Android properties (name-length limits).
  That profile also skips shader priming and the boot animation, which softpipe draws too slowly ([QEMU spec](qemu.md)).
- The laptop menu selects AMD only for PCI `1002:15e7`; otherwise softpipe is the default.
  [graphics-amd.rc](../../hardware/msi-modern-15-b7m/system_ext/graphics-amd.rc) selects Google's ANGLE GLES,
  RADV Vulkan RenderEngine and Mesa GBM/Zink, with GL HWUI like QEMU. The AMD-only Vulkan HWUI
  entry is opt-in. The RADV queue patch is compiled into the driver used by both AMD profiles;
  it maps logical queues onto hardware rings and serializes submissions per context. Keep GL as
  the default; the owner saw no noticeable improvement with the optional profile.
- LineageOS minigbm's Mesa backend needs the small AMD/FD/mapping fixes in
  [minigbm-amd.patch](../../hardware/drivers/amdgpu/minigbm-amd.patch). Its C++ interface links to Google's actual
  platform libraries, not NDK libc++; an ABI gate checks Google's clients whenever either image or library changes.
- [mesa-drm-master.patch](../../hardware/drivers/drm-handoff/mesa-drm-master.patch): Mesa drops DRM master after
  opening the primary node, so the composer can drive the display. A source patch, no added privileges.
- Reuse the owner's gbos video findings at source level, not its binary patches.
  External-only AHB formats use Mesa's common gralloc query; planar YUV fallback allocations
  have 256-byte-aligned chroma pitches for RADV. Keep directly supported formats unchanged.
- QEMU loads Google's virtio-gpu; the laptop adds amdgpu with official firmware.
  Graphics properties: [android/vendor/build-prop.patch](../../android/vendor/build-prop.patch);
  DRM node labels: [file-contexts.patch](../../hardware/msi-modern-15-b7m/vendor/file-contexts.patch).
- Live uevents are serialized to prevent a delayed simpledrm remove event deleting amdgpu's reused
  card0. Only the MSI GPU's identification files get an existing SELinux type (`sysfs_gpu`, the
  same file set Google labels for its own GPU); no allow rules change.
- Use Churro's earlier PCI framebuffer handoff so the real GPU can take card0; preserve
  simpledrm for early output. It affects PCI display drivers in QEMU as well as the laptop.
- No host-GPU passthrough.

## Files
- [scripts/mesa.sh](../../scripts/mesa.sh) — Mesa/libdrm/Expat build; build cache keyed by inputs.
- [mesa-radv-two-queues.patch](../../hardware/drivers/amdgpu/mesa-radv-two-queues.patch) and
  [graphics-amd-vulkan.rc](../../hardware/msi-modern-15-b7m/system_ext/graphics-amd-vulkan.rc) — opt-in Vulkan HWUI
  test candidate.
- [scripts/minigbm.sh](../../scripts/minigbm.sh), [tools/minigbm_abi.py](../../tools/minigbm_abi.py) — incremental allocator build and platform ABI gate.
- [tests/gbm-wrapper.c](../../tests/gbm-wrapper.c), [tests/test_mesa.py](../../tests/test_mesa.py) — FD/error handling and unchanged-output publication.
- [scripts/ndk.sh](../../scripts/ndk.sh), [scripts/source.sh](../../scripts/source.sh) — NDK and patched source trees.
- [mesa-drm-master.patch](../../hardware/drivers/drm-handoff/mesa-drm-master.patch) — Mesa source patch.
- [android/vendor/install.list](../../android/vendor/install.list), [android/vendor/build-prop.patch](../../android/vendor/build-prop.patch) — Mesa libraries and settings in vendor.
- [mediaswcodec.policy](../../android/vendor/mediaswcodec.policy) — additive software-codec
  seccomp policy for Mesa's CPU-affinity query; the platform sandbox and enforcing SELinux remain.
- [mesa-radv-yv12.patch](../../hardware/drivers/amdgpu/mesa-radv-yv12.patch),
  [minigbm-yuv-pitch.patch](../../hardware/drivers/amdgpu/minigbm-yuv-pitch.patch),
  [test_video_buffers.py](../../hardware/drivers/amdgpu/tests/test_video_buffers.py) — source-level external-format query
  and planar pitch fixes based on the owner's earlier gbos findings.

## Verify
`make test`, `make mesa JOBS=12`, `make android-image JOBS=12`, then
`make qemu-check JOBS=12`. Open `out/qemu/screen.png` and look at it:
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
- Meson caches machine-file binaries, including the pkg-config environment. Reconfiguring,
  even with `--clearcache`, retained the old static dependency path. Key the VA build directory
  by its cross-file contents; do not wipe source trees or suppress duplicate symbols.
- RADV's Android strict mode caps the reported Vulkan version at 1.1. Google's camera effects
  request DRM modifiers without the pre-1.2 image-format-list dependency; native capabilities
  need upstream `android-strict=false`, not a guessed version override or a binary patch.
- RADV on GFX9 rejects linear AHWB planes whose pitch is not a multiple of 256 bytes
  (`INVALID_DRM_FORMAT_MODIFIER_PLANE_LAYOUT`). Spoofed YUV allocations in minigbm must align
  NV12/NV21 widths to 256 and YV12 luma to 512.
- Meson strips even skipped install targets. Install into the build cache, then publish only changed
  bytes; otherwise an unchanged build rewrites library timestamps.

## Actions
- [ ] Confirm the laptop compositor and HWUI renderer — done when SurfaceFlinger's or HWUI's
  output from a laptop boot names ANGLE/RADV rather than a software renderer (apps already do).
- [ ] Plan accelerated rendering in QEMU (e.g. virgl or Venus with host Mesa) — done when
  options, trade-offs and a recommendation are agreed with the user. Not approved to implement.

### Ideas (not approved)
- llvmpipe instead of softpipe as a cheaper speed-up (needs LLVM for Android).

## Handoff log
- 2026-11-04 (this commit) — Owner accepts Lenovo test; saved `193204` logs show no HttpEngine
  trap samples, with 190,311 SHA/148,506 GFNI/5,654 VNNI maxima over ~351 s, not CPU measurements.
  Video raises CPU; playback decoder, dedicated HttpEngine HTTP/TLS and MSI regression unverified.
- 2026-11-04 (this commit) — Separate portable HttpEngine crypto builds from Chromium's exact pin;
  29 tests, 323 exact exports, image/metadata/no-write repeat and enforcing QEMU/native probe pass.
  Actual HTTP/TLS request, Lenovo trap reduction and MSI regression remain unverified.
- 2026-11-04 (this commit) — Owner confirms faster Lenovo Chrome launch/page loads.
  Logs `20261104-185222`: 284,898 SHA-256 traps/~160 s versus 49,743,288/~605 s before;
  not matched workloads or a CPU benchmark. Conscrypt storm absent; MSI crypto regression pending.
- 2026-11-04 uncommitted — Integrated portable BoringSSL into system/vendor and Conscrypt only;
  66 focused tests, image metadata, enforcing QEMU setup/mounts/crypto/HTTPS checks pass.
  Repeat preserves timestamps with no partition writes. Lenovo CPU and MSI regression await hardware.
- 2026-11-04 uncommitted — Lenovo SHA-256 emulation reaches 49.7M traps in ~10 minutes.
  Standalone `make boringssl JOBS=12` builds upstream with CPUID dispatch: all 2693 crypto/637 SSL
  exports match system/vendor; 14 tests and no-write publication repeat pass. Not installed/tested in Android.
- 2026-11-04 uncommitted — Owner confirms Chrome renders on the Lenovo with the hasvk patch.
- 2026-11-04 uncommitted — Lenovo Chrome grey: GPU process logged "could not create backing" and
  restarted; root cause hasvk's AHB format query. Added the one-condition Mesa patch; 271 tests,
  image and QEMU (softpipe, does not exercise hasvk) pass. Lenovo Chrome retest pending.
- 2026-11-04 uncommitted — Added hasvk (`vulkan.intel_hasvk.so`, 22 MB) for the Lenovo camera;
  Intel profile keeps GL rendering. Image fits, QEMU setup screen inspected; Lenovo camera/Chrome untested.
- 2026-11-04 uncommitted — Recipe source/profile bytes and image outputs match baseline;
  263 tests, metadata checks, no-write repeat and inspected direct/UEFI softpipe boots pass.
  Physical AMD/Intel regression remains with the owner.
- 2026-11-04 uncommitted — Moved Mesa/minigbm patches and graphics profiles into recipes;
  retained exact profile contents and explicit patch ordering. Not validated.
- 2026-11-04 (this commit) — Kernel display fixes moved unchanged into AMD/i915 recipes;
  40 source/recipe/module tests and image preservation checks pass. No new runtime boot.
- 2026-11-03 (this commit) — Owner confirms Lenovo guest/another-profile desktop and video,
  with good perceived performance. Successful boot has no prior framebuffer errors; original-
  profile freeze lacks panic evidence. Wi-Fi/touchpad work is tracked in the hardware spec.
- 2026-11-03 (this commit) — Lenovo i915/Iris confirmed; fb -22 after animation matches
  Churro's primary-alpha fix. Reused patch passes build/33 tests/no-write repeat and enforcing
  QEMU setup/input (screens inspected); Lenovo hardware retest remains, Bluetooth separate.
- 2026-11-03 (this commit) — Iris/exact-ID Intel GLES integrated into the normal fresh expanded
  image; direct and USB/UEFI enforcing QEMU reach inspected setup. Old disk/USB untouched;
  owner Lenovo GPU binding and MSI regression remain.
- 2026-11-03 `uncommitted` — Iris and exact-ID Intel GLES profile built; 69 tests, separate
  partition metadata/fit and enforcing direct/UEFI QEMU pass (screens and input response viewed).
  Working disk/USB untouched; migration, Lenovo GPU binding and MSI regression still pending.
- 2026-11-02 (this commit) — Corrected camera evidence and RADV patch scope; broad app-rendering
  regression checks and the webcam LED's cause remain unverified.
- 2026-11-02 `a5befdb` — Owner confirms the camera works with native RADV capabilities for
  effects, VA initialization and 256-byte NV12/NV21 pitches.
- 2026-11-02 `a5befdb` — Physical camera now initializes VA; effects fail Vulkan dependencies
  under RADV's strict-mode 1.1 cap. Native-capability option passes 22 tests, image checks,
  no-write repeat and enforcing QEMU (screen inspected); physical rendering/capture pending.
- 2026-11-02 `a5befdb` — Black preview persists; inherited Zink conflicts with JPEG-only
  RadeonSI. Service-only clearing passes 21 tests, image read-back/no-write repeat and enforcing
  QEMU (screen inspected). Physical retest pending.
- 2026-11-02 `a5befdb` — Separate JPEG-only RadeonSI and shared AMD DRM helper build;
  20 tests, shipping ELF imports/bytes, image metadata/fit, no-write repeat and enforcing QEMU
  pass (screen inspected). Google runtimes/rendering unchanged; laptop preview/capture pending.
- 2026-11-02 (this commit) — Owner confirms video fixed after the YV12 update, then the previously
  failing game, another native app and Hearthstone working with Berberis. Native-bridge comparison
  and isolated crash capture are tracked in the boot spec; no new graphics changes.
- 2026-11-02 (this commit) — Owner reports desktop crash on video after the sandbox fix. Ported
  prior gbos YV12 findings as source fixes: common format query and aligned chroma pitch. 131 tests,
  vendor build/ABI checks and enforcing QEMU pass; not deployed, new crash signature unconfirmed.
- 2026-11-02 (this commit) — Software codecs crash on Mesa's affinity query; added one vendor
  seccomp rule. 16 tests, vendor rebuild/no-op repeat, enforcing QEMU and software AVC encoding pass.
  Owner reports HDMI fine and no Vulkan HWUI speed difference; laptop video fix awaits deployment.
- 2026-11-02 `uncommitted` — Opt-in RADV two-queue Vulkan HWUI candidate builds; `make test`,
  Android image sync and QEMU softpipe check pass. Laptop Vulkan entry remains untested.
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
