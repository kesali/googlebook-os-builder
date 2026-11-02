# Laptop hardware

**Status:** partial — the laptop completes setup over Wi-Fi with working input; physical sound
and screen brightness still fail on the last owner-tested image.
**Last verified:** 2026-11-02 — the owner booted `ec5d360` and reported no sound or brightness
adjustment. The new candidate builds with unchanged Google kABI; all 100 unit tests pass. Its enforcing
QEMU [setup](../../out/hardware-fixes-validation/qemu-final-production/screen.png) responds to a
[mouse click](../../out/hardware-fixes-validation/qemu-final-production/after-click.png);
both screenshots were inspected.
A disposable HDA fixture verifies card selection, scoped sysfs permissions, HAL restart and a
nonzero 1 kHz signal ([measurements](../../out/hardware-fixes-validation/qemu-audio-final/signal.json)).
That fixture uses QEMU mixer values, not the MSI's; physical confirmation is still required.

## Goal
Run Googlebook OS on the **MSI Modern 15 B7M** (Ryzen 5 7530U, Radeon Vega graphics,
MT7922 Wi-Fi/Bluetooth, ELAN touchpad, HDA/ACP audio), following the working Churro baseline
with readable source changes and incremental USB updates.

## Current state
Verified on the laptop: the normal framebuffer-handoff boot, setup over Wi-Fi, keyboard and
touchpad. The owner finds app launches/graphics faster than Churro and gbos-x86; this is an
impression, not a benchmark. Density 160 replaces 180 in the AMD profile only; QEMU keeps 240.
GPU acceleration, Bluetooth, microphones and suspend have not been independently verified.

The latest USB hardware snapshot could not be retrieved with the available access. Investigation
therefore used the references, Google's HALs and this laptop's **host Linux** hardware, read-only
([evidence](../../out/hardware-fixes-validation/host-hardware.txt)):

- Analog HDA at `03:00.6`: ALC256, usually card1/`Generic_1`; HDMI at `03:00.1` is a different
  card. Card numbers and `Generic` IDs are not reliable selectors.
- Google's audio HAL requires its mapped `sofrt5682` card ID and board configuration.
  The candidate selects `chip_name=ALC256`, renames only that card, verifies the ID and restarts
  the HAL after readiness. Declarative XML maps Speaker/Headphone/Mic to analog PCM 0 and
  unmutes the host-observed mixer controls. Internal ACP mic and HDMI routes are not implemented.
- Native panel backlight is under the GPU's `cardN-eDP-1`, with `max_brightness=65535`.
  Google's lights HAL accepts `backlight`, but not `amdgpu_blN`. The source patch gives only
  this model's first AMD panel that supported name; the driver/scaling algorithm is unchanged.
  Its sysfs files use the HAL's existing `sysfs_leds` permissions.
- The new image contains these candidates and a readiness-gated, read-only hardware snapshot.
  QEMU checks do not prove the physical ALC256 mixer or AMD backlight works.

The regular image is [out/android/disk.img](../../out/android/disk.img), **53,430,190,080 B**
(49.8 GiB), not the separate diagnostic OS. The BUP Slim USB retains its own Android accounts
and data. This work updated only the regular image; no physical disk was written or host restarted.

| Part | Device [ID] | Driver / status |
|---|---|---|
| Display / GPU | Radeon Barcelo [1002:15e7] | `amdgpu`; usable desktop, acceleration not measured |
| Keyboard | i8042 AT keyboard | `atkbd`; works |
| Touchpad | ELAN0307:00 [04f3:3282] | AMD I2C, `i2c_hid_acpi`, `hid-multitouch`; works |
| Wi-Fi | MT7922 [14c3:0616] | `mt7921e`; setup completed over Wi-Fi |
| Bluetooth | MediaTek USB [0e8d:0616] | Not verified |
| Audio | HDA [1022:15e3], HDMI [1002:1637], ACP [1022:15e2] | ALC256 candidate awaits physical retest |
| Camera / SD reader | USB [30c9:0042], [0bda:0129] | Later |
| Storage | Samsung PM9C1a NVMe [144d:a80d] | Hidden from laptop Android; boot from USB |

## Decisions
- Laptop first; QEMU setup is a regression check, not a second product. No installer or dual boot.
- Use the working Churro baseline, source changes and official firmware. Keep softpipe fallback,
  Google's ANGLE, RADV RenderEngine, GL HWUI and Mesa GBM/Zink ([graphics](graphics.md)).
- Build only missing modules, sign with the kernel's trusted key and retain Google's helpers.
  No ABI-whitelist relaxation. The agreed early display/touchpad dependencies stay built in
  ([kernel](kernel.md)); do not change touchpad drivers while repairing another component.
- GRUB detects GPU `1002:15e7` and selects the AMD profile. Density 160 is laptop-only.
  Keep `console=drm_log`, `initcall_blacklist=nvme_init`, the TPM/SPI-flash blacklist and EFI
  pstore safeguard. The framebuffer-free experiment panicked; use the normal entry.
- Same disk layout for QEMU and USB: Google's EFI-SYSTEM absorbs only blank `KERN-A`, becomes
  576 MiB FAT32 `DALI-BOOT` and retains its PARTUUID. Other partitions and data stay intact.
- Boot files update through the mounted ESP with [deploy.py](../../tools/deploy.py): new files
  first, menu last, previous build retained. `make deploy-android` selects the Android bundle;
  `make deploy` is the diagnostic OS. The image's ESP uses mtools without root or mounts.
- Only the owner transfers OS partitions, with the reviewed USB by-id identity, layout checks
  and read-back. Never reflash over existing data or run recovery on the physical USB.
- Wi-Fi uses the signed mt76/MT7921E chain, Google's mac80211/cfg80211 and pinned official
  firmware. Keep `mt7921_common.disable_clc=1`; validate imports against Google's modules.
- Keep Google's HDA/audio and lights HALs. Remove the Lenovo HDA blocklist/SOF override.
  Audio preparation is AMD-profile-only, matches ALC256, is bounded, logs failures and signals
  readiness only after verified renaming. SELinux permits writing only this analog controller's
  card-ID file. No generic sysfs write grant, bind mounts or replacement HAL.
- Mixer XML uses measured ALC256 controls: mono Master and stereo Speaker/Headphone, volume
  87 = 0 dB; capture defaults off, with 23 = 0 dB when the Mic route is selected.
  Do not advertise missing HDMI/ACP PCMs as working microphones or outputs.
- Backlight naming is restricted by exact DMI vendor/model and the first panel; other machines
  retain upstream names. Drop the patch when the unchanged HAL can discover AMD backlights.

## Files
- [kernel/gki.config](../../kernel/gki.config), [laptop-modules.list](../../kernel/laptop-modules.list),
  [msi-firmware.list](../../kernel/msi-firmware.list) — explicit drivers and firmware.
- [kernel/msi-backlight.patch](../../kernel/msi-backlight.patch) — narrow panel-name adaptation.
- [android/vendor/get_variant_audio](../../android/vendor/get_variant_audio),
  [audio-msi.rc](../../android/vendor/audio-msi.rc), [audio-msi.patch](../../android/vendor/audio-msi.patch)
  — card selection, readiness-triggered restart and declarative PCM/mixer configuration.
- [audio-policy.patch](../../android/vendor/audio-policy.patch),
  [file-contexts.patch](../../android/vendor/file-contexts.patch) — scoped labels/permissions.
- [android/vendor_dlkm/modules.patch](../../android/vendor_dlkm/modules.patch) — codec preload/HDA unblock.
- [hardware-snapshot.sh](../../android/system_ext/hardware-snapshot.sh) — read-only physical evidence.
- [tests/test_audio.py](../../tests/test_audio.py), [test_kernel_source.py](../../tests/test_kernel_source.py)
  — selector failures, exact card-ID bytes and model-specific backlight naming.
- Reference ports (local, not in Git): `reference/project-churro-msi-modern-15-B7M`,
  `reference/gbos-x86-msi-modern-15-B7M`.

## Verify
1. `make test`, then `make android-image JOBS=12`. Check kABI/filesystem metadata and a repeat
   build: unchanged outputs must preserve timestamps and write no partitions.
2. Boot a disposable copy with enforcing SELinux; inspect setup and an actual input response.
   The [validation driver](../../out/hardware-fixes-validation/check.py) records this evidence.
   Its audio fixture changes the expected codec to `Generic` and uses QEMU's measured stereo
   Master (0–74), while production uses ALC256's mono Master (0–87). It captures WAV only,
   never host speaker output. A zero-filled WAV is **not** audio success.
3. Follow the [Android update workflow](../../README.md#updating-the-existing-android-usb).
   This candidate changes vendor, system_ext, vendor_dlkm and boot files; both boot-file and
   OS-partition updates are needed. Do not select the previous or framebuffer-free menu entry.
4. Owner retest: start with low Android volume, play media, check speakers/headphones and move
   the brightness slider. Confirm density/input/Wi-Fi remain usable. Retrieve the new snapshot
   and relevant logs whether the result succeeds or fails.

### Recovering the new boot logs
After returning to Linux, use the checked USB by-id path, not an ambiguous `/dev/sdX`. Metadata
is currently partition 17; verify the layout. Mount it `ro,noload` or read it with debugfs and
copy only `/dali-bootlog/current/` and `previous/` into a pre-created ignored evidence directory.
The files are owned by logd, so retrieval may require the owner's locally authorized sudo.

Each boot contains `boot-id`, `boot.txt`, rotated kernel/Android logs and `hardware.txt`.
The snapshot records backlight values/permissions/SELinux labels, ALSA IDs/codecs and modules.
Keep app/account logs private; share only relevant filtered excerpts.

An unclean shutdown can leave stale inodes. Ask before copying metadata (which also contains
security state) to private tmpfs for journal replay; verify no disk-backed swap, recover only
on that regular copy and remove it afterwards. Never repair the USB directly. A hang before
metadata/logd starts still needs a screen photo.

## Pitfalls
- ALSA's `id_store` rejects a trailing newline. The selector must write exactly `sofrt5682`,
  not `echo` it. The enforcing QEMU test caught this; the regression checks exact bytes.
- `stdio_to_kmsg` is ignored on user builds. The audio selector uses Android `log` so errors
  reach persistent diagnostics; unit tests alone cannot establish this behavior.
- Hardware card numbers change; QEMU's mixer is not ALC256. Never copy QEMU's stereo Master
  values into the laptop's mono control.
- The audio ID is deliberately unreadable to the serial shell. Its `ls` denial is not a HAL
  failure; the selector, HAL and read-only hardware snapshot have scoped read access.
- libdrm needs all GPU identification labels at `00:08.1/03:00.0`, not just `uevent`.
  Missing labels caused the earlier SurfaceFlinger/zygote loop. The framebuffer handoff then
  fixed the visible display; the old framebuffer-free experiment caused a separate hard lockup.
- A saved previous GRUB menu may predate the EFI safeguard. Old UEFI crash records are untouched.
- Prefer a USB 3 cable/port: the BUP Slim was observed at USB 2.0, about 39 MB/s sequential reads.
- A kernel log, boot-complete property or correctly sized PNG does not prove a usable desktop.

## Actions
- [ ] Physical audio retest — done when the owner hears media through speakers/headphones;
  inspect the new snapshot/logs if silent.
- [ ] Physical brightness retest — done when the setting visibly changes the panel; confirm
  the new backlight name and label in the snapshot.
- [ ] Confirm laptop density 160 remains comfortable, with QEMU still 240.
- [ ] Diagnose the old framebuffer-free hard lockup only with a safe, evidence-based test.
- [ ] Establish whether the touchpad needs `X86_AMD_PLATFORM_DEVICE` through a separately
  agreed diagnostic A/B test; leave the working production input path unchanged.

### Ideas (not approved)
- Bluetooth, internal ACP microphone, HDMI audio, battery/suspend bring-up.
- Generalize the local OS updater only if needed; no passwordless physical-write udev rule.

## Handoff log
- 2026-11-02 (this commit) — ALC256 routing/mixer and MSI-only backlight naming built; scoped
  enforcing audio selection and a real 1 kHz QEMU signal verified with a test-only mixer.
  No physical writes/reboot. Next: owner updates both boot and OS files and retests hardware.
- 2026-11-02 `ec5d360` — Density 160, HDA unblock and read-only snapshot built and QEMU-checked.
  Owner subsequently booted it; sound and brightness still fail.
- 2026-11-02 `ab9d9c5` — Owner updated the USB and completed setup over Wi-Fi; input works.
  UI feels fast, not benchmarked. Sound and brightness are the remaining reported failures.
- 2026-11-02 `3f7ce26` — Source-level framebuffer handoff reached physical setup with input.
  Earlier framebuffer-free test panicked; keep the normal entry and EFI safeguard.
