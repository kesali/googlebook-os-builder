# Patch audit (2026-11-05)

Each source patch and the larger Android text patches were checked against current upstream
to find anything we can drop or simplify. Pins at the time: kernel `android17-6.18-2026-06_r52`,
Mesa `26.3.0-rc3` (26.3.0 is not final; latest stable 26.2.6), LineageOS minigbm `51b9743`
(upstream head `0111c9e`, no relevant changes). Upstream findings came from git.kernel.org,
lore.kernel.org, gitlab.freedesktop.org Mesa `main` and the LineageOS minigbm repository.
Re-check when a pin changes.

## Source patches

| Patch | Upstream today | Verdict |
|---|---|---|
| [mesa-radv-yv12.patch](../hardware/drivers/amdgpu/mesa-radv-yv12.patch) | RADV's `radv_android.c` still sets `format`/`externalFormat` without handling `VK_FORMAT_UNDEFINED`; Mesa's common `vk_android.c` handles it but RADV does not call it. Removing it crashed SurfaceFlinger on the MSI when video opened. | Keep; upstream candidate |
| [minigbm-yuv-pitch.patch](../hardware/drivers/amdgpu/minigbm-yuv-pitch.patch) | Spoofed-format allocations only pad the total size; newer `fca29af3` only unifies 32-byte camera/codec alignment. | Keep |
| [mesa-hasvk-ahb-format-query.patch](../hardware/drivers/i915/mesa-hasvk-ahb-format-query.patch) | Mesa `main` hasvk still requires `VkExternalImageFormatProperties`; anv moved to common `vk_android` code without that gate. | Keep; easy upstream candidate |
| [mesa-drm-master.patch](../hardware/drivers/drm-handoff/mesa-drm-master.patch) | `platform_android.c` still opens the primary node for software rendering and never drops master. `EGL_FORCE_RENDERNODE` would break the softpipe path. | Keep |
| [msi-backlight.patch](../hardware/drivers/amdgpu/msi-backlight.patch) | No kernel option renames a backlight; `acpi_backlight=` only selects the driver. Google's lights HAL is closed, so a path setting cannot be confirmed. | Keep |
| [renoir-capture-buffers.patch](../hardware/drivers/renoir-acp/renoir-capture-buffers.patch) | `rn_acp3x.h` limits unchanged; the generic `sound/soc/amd/acp` driver adds Renoir resources but no relaxed limits. | Keep |
| [i915-gen4-primary-alpha.patch](../hardware/drivers/i915/i915-gen4-primary-alpha.patch) | Mainline `i965_primary_formats` still lacks ARGB/ABGR8888. | Keep |
| Firmware framebuffer handoff (removed) | Upstream card0/card1 handoff issue avoided by disabling sysfb/simpledrm instead. | Owner confirms firmware-free boots on both laptops; rebuild/kABI/QEMU pass |
| [vex-emulate.patch](../hardware/drivers/cpu-vex/vex-emulate.patch) | Needed while Google's userspace targets Panther Lake. | Keep |

## Simplification candidates

**Firmware-framebuffer removal implemented and locally validated.** The owner confirmed the
no-firmware-framebuffer GRUB entry boots on both MSI and Lenovo, and MSI video works.
The [drm-handoff config](../hardware/drivers/drm-handoff/gki.config) now disables sysfb/simpledrm.
The handoff kernel patch, ueventd serialization patch and temporary test entry are removed.
Normal DRM screen logging is disabled too, avoiding an extra DRM client module solely for
boot logs. `earlycon=efifb` remains in the debug entry; saved diagnostic logging is unchanged.
Normal boots have no kernel screen log. 81 focused tests, kernel/image/kABI/module checks,
a 22 s no-write repeat and inspected direct/UEFI QEMU pass
([evidence](../out/native-framebuffer-removal/)).
The rebuilt image still needs a physical retest; brightness was not separately reported
in the owner's earlier test.

**Instruction emulation is still in active use.** Rate-limited emulator lines in the MSI's
latest boots still show `gf2p8affineqb` from ART's JIT (about 300k–430k total traps per boot)
and occasional `vpdpwssd`; earlier boots also showed SHA, VAES and VPCLMULQDQ before the
portable crypto change. Lines are rate-limited, so absence of an opcode is not proof it is
unused; do not prune the vendored emulator from these logs.

## Done in this audit

- [powerhint.patch](../android/vendor/powerhint.patch) moved from the MSI recipe to shared
  vendor changes: the combined image applied it on every laptop already.
- [native-bridge.patch](../android/system/native-bridge.patch) header now says Berberis is the
  default and Houdini comes from its GRUB entry.

## Upstream candidates

- hasvk: drop the `VkExternalImageFormatProperties` requirement for Android hardware buffers,
  matching anv and RADV.
- RADV: report an external format for external-only AHB formats such as YV12, ideally by using
  Mesa's common Android hardware-buffer query.

Both are small, reproducible fixes; once merged and pinned, the matching local patch is dropped.
