# How Bliss OS / Bass OS, PrimeOS and Android-x86 get broad x86 hardware support

Researched 2026-11-14. Primary sources only (public GitHub repos/docs, vendor site). No builds, no devices, no code changed.
Tags: **[V]** verified in public source; **[C]** vendor claim only; **[?]** unknown/opaque.
Raw URLs are `raw.githubusercontent.com/<org>/<repo>/<branch>/<path>`; line numbers are as fetched 2026-11-14 and will drift.

## Bottom line
Breadth comes from a **fat, mostly-modular generic kernel + linux-firmware + Mesa/minigbm + runtime probing in init scripts**,
not from per-device images. Device-specific logic is small DMI/uevent quirk tables layered on top.
PrimeOS publishes almost nothing verifiable; its mechanism is **[?]**.

## Lineage
- Bass OS = patches + manifest on top of Bliss OS (`Bliss-Bass/bass-os:bass-12.1:README.md:3-5`); Bliss OS README says it is "based on AOSP & Android-x86" (`BlissRoms-x86/manifest:arcadia-x86:README.md`, intro). Some Bass add-ons are licensed/private (README:7-9) -> those portions **[?]**.
- Bliss manifest pulls Android-x86-derived pieces: `android-x86/00-remotes.xml:5` (osdn `android-x86` remote), `02-android-x86.xml` (alsa, libaudio, libsensors, thermal_daemon, drm_hwcomposer, minigbm, mesa 26.0, libdrm, `device/generic/firmware`) **[V]**. `gpu_mesa.mk:2` still carries the Android-x86 copyright header.

## 1. Kernel source / config / modules **[V]**
- Kernel: `android-generic/kernel_common` branch `hm/crimson` (Linux 6.6.129 per `Makefile`), plus `hm/crimson-surface` for Surface; out-of-tree drivers in `external/kernel-drivers` branch `6.6` (`manifest:android-x86/02-android-x86.xml:43-45`). Selection in `device_generic_common:BoardConfig.mk:155-163` (`KERNEL_DIR ?= kernel/x86/common`; Surface build switches dir and adds `nvme_core.default_ps_max_latency_us=0 pcie_aspm=off`).
- Config `arch/x86/configs/android-x86_64_defconfig` (10,948 lines): nearly everything is `=m`: DRM i915 (L6327), amdgpu (L6299), nouveau (L6321), radeon, vmwgfx, virtio-gpu, simpledrm; Wi-Fi iwlwifi/mvm (L3369), ath9k/10k/11k, brcmfmac, mt76/mt7921e (L3445), rtw88/rtw89 (L3531), many rtl8xxx; BT btusb + Intel/BCM/RTL/QCA/MTK; SOF audio (L7086), HDA; HID sensor hub (L7551), Intel ISH (L7582), Surface battery/touch; Android binder built-in (L9661-9663).
  `CONFIG_EXTRA_FIRMWARE=""` (L2083) and `FW_LOADER_COMPRESS_XZ=y` (L2087): firmware is **not** built into the kernel; it is loaded from userspace files.
- Extra out-of-tree modules: `external/kernel-drivers` holds openrazer, gslx680-acpi, bcm2079x_i2c_mod etc. (tree of `BlissRoms-x86/external_kernel-drivers:k5.12-b2`); documented recipe = drop module dir + generic `Android.mk` setting `EXTRA_KERNEL_MODULE_PATH_*` (`BlissRoms-x86/Documentation:development/porting-linux-drivers.md:5-25`).
- Module policy per device class: `device_generic_common:modules.blocklist` (`deferred nouveau/amdgpu/radeon`, blocklists of conflicting rtw88 USB/PCI) and `modules.options` (btusb reset, 8821au/cu options), installed via `device.mk:70-71`.
- CPU floor: builds target x86_64-v2 (`Documentation:knowledgebase/frequently-asked-questions/hardware-compatibility.md:9-12`). Native bridge (houdini / libndk_translation) are proprietary extracted libs (same file, L43) -> contents **[?]**.

## 2. Firmware **[V] for source, [?] for exact shipped set**
- `device/generic/firmware` = `android-generic/device_generic_firmware` (`02-android-x86.xml:22`); its README identifies it as a linux-firmware mirror (upstream gitlab.com/kernel-firmware/linux-firmware), with vendor LICENCE.* files. Silead touch firmware is separate (`vendor/silead/proprietary/firmware`, L23).
- Which blobs land in a given ISO, and how they are packaged, was not verified (needs a build/ISO inspection) **[?]**.

## 3. Graphics / Mesa / gralloc **[V]**
- Mesa 26.0 built in-tree: `BoardConfig.mk:110-114` (gallium: crocus iris i915 nouveau r600 radeonsi svga virgl zink softpipe llvmpipe; vulkan: amd intel intel_hasvk virtio swrast nouveau; VA-API + video codecs).
- `gpu/gpu_mesa.mk:11-46`: multiple hwcomposer.drm_* and gralloc.minigbm_* / gbm variants, ANGLE, SwiftShader, vulkan.intel/radeon/virtio/nouveau/lvp, amdgpu.ids, iHD/crocus/gallium VA drivers.
- Runtime selection, `init.sh:347-460` `init_hal_gralloc`: reads the bound DRM driver of `/dev/dri/card*` and picks HWC/GRALLOC by case (virtio_gpu -> drm_minigbm+minigbm_arcvm L391-395; nouveau -> minigbm_gbm_mesa L397-399; i915 -> minigbm, with gen<9 disabling planes/alpha L401-411; amdgpu/vmwgfx/xe -> minigbm L413-415); falls back to software (`HWACCEL=0`, L426-430). User overrides: `GRALLOC=`, `HWC=`, `HWACCEL=` on the kernel cmdline (`Documentation:knowledgebase/troubleshooting/graphics-troubleshooting.md:7-23`).
- Caveat: Bass docs say NVIDIA discrete GPUs are out of scope; Bass ships no closed NVIDIA driver (`Bliss-Bass/Documentation:Installation/x86_64-v2/hardware-compatibility.md:12,29`). Bliss FAQ says Nvidia "support but limited" (L35) -> vendor statement **[C]**.

## 4. Android HAL / userspace probing **[V]**
`device_generic_common:init.sh` is the core; started from `init.x86.rc:39` before late boot:
- Wi-Fi: unload `wl` unless it is the bound driver (L46-50); brcm HAL (L128+). Bluetooth: per-chipset modprobe/btattach/UART logic (L270-314).
- Audio: modprobe snd_hda_intel, ALSA card probing, HDMI PCM guess (L76-124). CPU freq fallback `modprobe acpi-cpufreq` (L31).
- Sensors `init_hal_sensors` (L707-802): uses a board-specific `sensors.<hw>.so` if present, else IIO or kbd-sensor HAL; ACPI-ID (`UEVENT`) cases set accel order/scale quirks (e.g. `*EVE1494E*`, L719-730).
- Surface: DMI `product_name`/`product_sku` match -> `iptsd` hidraw device (L805-822). `init.x86.rc:148-156` iptsd services; `idc/` has ~25 touch/touchpad input-config files; thermal_daemon (`device.mk:134-135`).
- HAL repos from Android-x86 lineage: `hardware/libsensors`, `intel/libsensors`, `libaudio`, `libbt-vendor-intel`, `gps`, `liblights` (`02-android-x86.xml:9-19`).

## 5. Device-specific boot/config logic **[V]**
- Boot: kernel cmdline params for debug/graphics (`DEBUG=`, `GRALLOC=`, `HWC=`); Bass additionally documents boot options/boot-config (`Bliss-Bass/Documentation:UserGuides/bass-boot-options.md`, `boot-config.md` - titles only, content not read).
- Installer/boot stack: Bliss uses `bootable/aaropa` (Calamares-based, `04-custom.xml:4`); Bass has `bootable_aaropa` + `newinstaller` dirs in `bass-os` root. Their hardware detection was not read **[?]**.
- Build-time variants: Surface/Go builds (`BOARD_IS_SURFACE_BUILD`, `BOARD_IS_GO_BUILD`, `BoardConfig.mk:151-160`).
- Compatibility tracking is empirical: `BlissRoms-x86/CompatibilityList`, tested.blissos.org (`hardware-compatibility.md:3-5`); Bass derives its list from linux-hardware.org DMI data and warns absence != unsupported (Bass hw-compat doc L15). Support claims such as "Fully Supported" are maintainers' tables **[C]**.

## PrimeOS
- Official site (primeos.in -> primebook.in/primeos) is marketing only: apps, office suite, 3 years of security updates, Primebook-bundled (fetched 2026-11-14). No kernel, driver, firmware or HAL statements **[C]/[?]**.
- No official PrimeOS GitHub org found. Third-party repos labeled "PrimeOS x86 kernel source" exist (e.g. `GuneetAtwal/android_kernel_common`, branch `kernel-4.19-stock`, author-labelled, unofficial; `floydwiz-tech/android_kernel_common`). Treat as **unverified provenance**; their configs/modules were not analysed.
- PrimeOS userspace, firmware, graphics and installer: **[?] (proprietary/undisclosed)**. Do not infer it matches Bliss/Android-x86.

## Android-x86 (where relevant)
- Project goal: port AOSP to x86 (android-x86.org home page); original source host osdn. Bliss manifest still pulls pieces via remote `x86` (osdn) and `ag-github` forks. The upstream Android-x86 tree itself (osdn gitroot) was not browsed here; mechanisms above are from its maintained descendants **[V for descendants, ? for upstream today]**.
- Heritage visible in code: `init.sh` structure, `idc/`, `gralloc`/`hwcomposer.drm` options, `kernel-drivers` Android.mk recipe.

## Mechanisms vs this repository (high level only)
This repo already has analogues: shared kernel options (`kernel/gki.config`), `kernel/firmware.list`, `kernel/laptop-modules.list`, per-device recipes under `hardware/`, Google's GKI as kernel base (`docs/research/kernel-vs-ruby-image.md`). Differences visible from the sources above: Bliss runs a *community* 6.6 kernel with an all-modules superset and runtime HAL probing in a shell script; this repo pins Google's GKI/Ruby base and adds drivers as audited recipes. Not evaluated: ABI/signing implications of copying Bliss's out-of-tree module approach onto GKI (Bliss does not appear to preserve Google kABI; not verified).

## Local-project comparison before runtime graphics selection
This comparison records the earlier design that motivated separating graphics selection
from device quirks. The current selector and remaining limits are in
[the graphics spec](../specs/graphics.md). Local artifact inspection is not runtime proof.

Counts are approximate and come from inspecting local/unpacked images, not from booting them.
- **Stock Ruby images:** `vendor_dlkm` has ~484 `.ko`; `system_dlkm` ~100. `vendor_a` carries some Intel Wi-Fi, MediaTek, RTL, i915/xe and Cirrus/audio firmware.
- **Tracked add-on module set** (`kernel/laptop-modules.list`, recipes under `hardware/drivers/`) includes modules absent from stock, e.g. amdgpu and i915 (`hardware/drivers/amdgpu`, `hardware/drivers/i915`). So breadth is a curated delta over Google's set, unlike Bliss's superset kernel. Whether stock firmware covers each added module's blobs is not established here.
- **Selector overload (risk):**
  - `boot/android-menu.cfg:28-37` defaults `gbos_builder_graphics=softpipe` and sets `intel`/`amd` only for exact known IDs; passed as `androidboot.gbos_builder.graphics=` (L42).
  - `android/system_ext/gbos-builder.rc:2` imports `graphics-${ro.boot.gbos_builder.graphics:-softpipe}.rc`.
  - The same value also gates device quirks: `hardware/msi-modern-15-b7m/system_ext/graphics-amd.rc:11-12` sets panel density 160; `hardware/msi-modern-15-b7m/vendor/audio-msi.rc:2` triggers on `graphics=amd`; `hardware/lenovo-e50-80/vendor/audio-lenovo.rc:3` and `.../system_ext/display-lenovo.rc:4-5` trigger on `graphics=intel`.
  - Consequence: if detection is made generic (any AMD/Intel GPU gets `amd`/`intel`), every such machine would also receive MSI's density/audio or Lenovo's audio/display quirks. Today the exact-ID gate prevents this only by accident.
  - **Recommendation (no code changed):** before generalizing, split GPU backend choice (a graphics property) from device identity (e.g. DMI-derived product/board property) and key quirk `.rc` triggers on the latter. Compare Bliss: backend is chosen from the bound DRM driver (`init.sh:347-460`) while quirks key on DMI/ACPI IDs (`init.sh:719-822`) - separate mechanisms.

## Gaps
Exact modules/firmware in shipped ISOs; Bass private add-ons; Bass `newinstaller`/aaropa detection logic; PrimeOS entirely; upstream Android-x86 current state; Bliss 14+/Bass kernel branches other than `hm/crimson`.
