# Laptop hardware

**Status:** partial — Wi-Fi, input, speakers, built-in microphone, camera and video work by owner
report. HDMI display performance feels fine; the brightness slider is unconfirmed.
**Last verified:** 2026-11-04 — Recipe integration: 263 tests, exact declaration/asset/patch
comparison, all 4,501 exports, signed-module metadata and image-fit checks pass. All 38 tracked
output hashes match baseline; 23.8 s repeat preserves timestamps with no partition/boot writes.
Disposable enforcing QEMU setup/input and USB-UEFI pass; no physical MSI/Lenovo retest.
[Evidence](../../out/full-hardware-recipes/).

Earlier, 2026-11-02 — owner confirms camera preview and video recording work after the
NV12 pitch update. Its LED also flashes under Linux; the cause is unknown
([logs](../../out/laptop-logs/20261102-231851-2bm_5yev/current/)).
Earlier, the owner confirmed the microphone works after the Renoir buffer update.
The driver, InternalMic route and buffer patch pass focused tests, ABI/image checks, no-write
repeat and enforcing QEMU ([evidence](../../out/renoir-buffer/)). No fresh capture logs or
recording-quality measurements were supplied with the owner report.
Earlier, the owner confirms video playback is fixed and the previously
failing game, another native app and Hearthstone work with the optional Berberis boot entry.
This is owner-reported hardware verification; new laptop logs have not been retrieved.
Earlier, the owner booted `95b3bf6`: sound works; frame rate halves with
HDMI connected. Its [snapshot](../../out/laptop-boot-2026-11-02-hdmi/current/hardware.txt) shows
`/sys/class/backlight/backlight` labelled `sysfs_leds`, brightness 51750 of 62451. Commits after
`95b3bf6` (HDMI page flips, generic bionic/libz, polling fixes, TPM wait, power HAL CPU masks)
reached the stick on 2026-11-02 (see Current state). The owner subsequently tested it: HDMI
performance seems fine, and the opt-in Vulkan HWUI profile makes no noticeable speed difference.
The [new logs](../../out/laptop-boot-2026-11-02-video/dali-bootlog/) contain normal AMD and
AMD-Vulkan boots; the subsequently deployed video fixes are in [graphics](graphics.md).

## Goal
Run Googlebook OS on the **MSI Modern 15 B7M** (Ryzen 5 7530U, Radeon Vega graphics,
MT7922 Wi-Fi/Bluetooth, ELAN touchpad, HDA/ACP audio), following the working Churro baseline
with readable source changes and incremental USB updates.

## Current state
Verified: MSI audio/camera/power policy and Lenovo IDC assets moved into device recipes;
driver configs, modules, aliases and firmware moved into reusable driver recipes.
The current selection still targets both laptops. Exact declarations/assets/patches and
rebuilt outputs match baseline. New physical testing on both machines remains with the owner.

Clean-break gbos-builder rename aligns vendor audio readiness/service names
with boot profiles and renamed SELinux types. No mixer, buffer, calibration or driver changes.
The log reader now reads only `/gbos-builder-bootlog`; historical local evidence is untouched.
246 tests, signed modules/image metadata and enforcing QEMU diagnostics pass
([evidence](../../out/gbos-builder-validation/)); renamed AMD audio services and physical
peripherals are not verified on hardware. Previous owner confirmations below predate the rename.

Lenovo Broadwell (2026-11-03): owner reaches desktop in guest and another profile and reports
good performance and working video; the first profile froze with flashing Caps Lock.
[Recovered failure logs](../../out/laptop-logs/20261103-184303-hottd2ca/recovered-current/)
contain no panic trace. The successful boot's
[logs](../../out/laptop-logs/20261103-185854-21kebgv7/current/) show Atheros `168c:0036`
Wi-Fi without ath9k, plus `ETD0630/PNP0F13` and an unbound PS/2 serio port; Google's config
disables `MOUSE_PS2`. Owner confirms Wi-Fi/touchpad do not work. Upstream ath9k and
psmouse/Elantech are the initial candidates. Ath9k is now wired with unchanged upstream source,
four signed modules and the exact device alias; it passes compile/import/CRC checks against
Googlebook's actual helpers. No new firmware is needed for this PCI ath9k path.
Final image validation passes: 40 tests, unchanged Google exports, signed dependencies/alias,
517 metadata entries, no-write repeat and enforcing QEMU setup/input (screens inspected).
Physical Wi-Fi testing remains. Owner then approved adding touchpad before the USB update:
upstream psmouse/Elantech and normal protocol defaults, with AUX hotplug and built-in libps2/I2C
helpers. Compiled psmouse has no module dependencies; libps2/I2C imports resolve in the kernel.
The combined candidate passes 41 tests, ABI/module/image checks, no-write repeat of 35
output/disk hashes/timestamps and enforcing QEMU setup/input (screens inspected).
The owner now confirms Wi-Fi works. Touchpad initialization and Android classification pass,
but single-finger movement stalls even without typing; the USB mouse and system remain usable.
The [latest logs](../../out/laptop-logs/20261103-193411-6wi12hz7/current/) show the Elantech v4
device (`0x594f03`) without retained packet/reset errors. Live CachyOS `7.1.6-1-cachyos`
works normally by owner report, using the same `ETPS/2` protocol, firmware and capability
values. This does not yet distinguish a kernel difference from Android input filtering.
The same Android boot shows a Chrome GPU-process abort, an audio HAL/card-name mismatch
despite ALC233 analog playback/capture enumeration, and an enumerated USB EasyCamera.
These are separate investigations, not evidence that all need new kernel drivers.
[Candidate validation evidence](../../out/lenovo-touchpad/).

Verified on the laptop: the normal framebuffer-handoff boot, setup over Wi-Fi, keyboard and
touchpad. The owner finds app launches/graphics faster than Churro and gbos-x86; this is an
impression, not a benchmark. Density 160 replaces 180 in the AMD profile only; QEMU keeps 240.
Video works after the source-level YV12 fixes. The owner reports the previously failing game,
another native app and Hearthstone work with Berberis; normal boot still selects Houdini.
See [boot](boot.md) for the translator comparison and its limits.
Chrome logs show ANGLE on RADV; SurfaceFlinger/HWUI, Bluetooth, headset microphone and suspend
have not been independently verified.
In the `95b3bf6` kernel log, Google's `btusb`/`btmtk` found the MT7922 Bluetooth but `hci0` setup
failed: `mediatek/BT_RAM_CODE_MT7922_1_1_hdr.bin` was missing. The official file is now installed.

Audio and backlight were designed from the references, Google's HALs and this laptop's
**host Linux** hardware, read-only ([evidence](../../out/hardware-fixes-validation/host-hardware.txt)):

- Analog HDA at `03:00.6`: ALC256, usually card1/`Generic_1`; HDMI at `03:00.1` is a different
  card. Card numbers and `Generic` IDs are not reliable selectors.
- Google's audio HAL requires its mapped `sofrt5682` card ID and board configuration.
  The candidate selects `chip_name=ALC256`, renames only that card, verifies the ID and restarts
  the HAL after readiness. Declarative XML maps Speaker/Headphone/Mic to analog PCM 0 and
  unmutes the host-observed mixer controls. HDMI routes remain unimplemented.
- Built-in mic: host Linux uses `snd_rn_pci_acp3x` at `03:00.5` with `acp` digital-mic capture.
  Android's pre-change snapshot has only HDMI/ALC256 PCMs. The driver-only image now includes
  upstream Renoir ACP modules and reuses Google's DMIC helper. Build/ABI/module metadata checks,
  29 focused tests and enforcing QEMU regression pass ([evidence](../../out/microphone-drivers/)).
  The owner updated and booted the USB; the [new snapshot](../../out/laptop-boot-2026-11-02-microphone/current/hardware.txt)
  confirms all five ACP/DMIC modules, card `acp` and its capture PCM. This driver-only stage
  did not yet provide microphone input in apps.
  The built route candidate maps `InternalMic` to `hw:acp,0`, preserves
  Google's stereo channel map and adds an empty mixer path (ACP needs no HDA capture controls).
  Existing `Mic` remains the analog headset input; speaker/headset selection, HAL and SELinux
  are unchanged. Google's inherited sensitivity is not a measured MSI calibration.
  The patched XML was read back from `vendor_a`, all 1,620 filesystem entries passed metadata
  checks, and 348,319,744 B fits the 387,108,864 B limit. Repeat build preserved published
  timestamps and wrote no partitions ([evidence](../../out/microphone-routing/)).
  With the route alone, the microphone slider appeared but diagnostic input was silent.
  HAL resolved ACP `(2,0)` and stereo S32_LE correctly, but its two-period buffers conflicted
  with Renoir's limits. After the isolated buffer patch below, the owner confirms the
  microphone works. Capture quality and speaker/headset regression were not separately reported.
- Camera: fresh boot `dd2faa0b-28c1-4ab4-8835-b42f924cc84c` shows the USB HAL registering
  `30c9:0042` on `/dev/video0`, camera ID 2, up to 1280x720; the owner reports "no camera"
  in a camera app. The HAL labels it external, and Google's internal-camera table omits this ID.
  Camera/front feature declarations already exist. No capture-open failure was found in the
  retained logs ([snapshot](../../out/laptop-logs/20261102-211552-18mjtoqx/current/)).
  Approved [camera-msi.patch](../../hardware/msi-modern-15-b7m/vendor/camera-msi.patch) adds only this USB ID with
  `FACING_FRONT`, without guessed calibration. 13 camera/overlay tests pass; the 25.9 s vendor
  rebuild reads back the exact intended table and verifies all 1620 filesystem metadata entries.
  Its 348,319,744 B image fits the 387,108,864 B limit. The 14.7 s repeat preserves 29 published
  file sizes/timestamps and writes nothing; bounded QEMU passes in 76.3 s (enforcing SELinux,
  stable services, setup screenshot inspected; input not retested).
  [Build evidence](../../out/camera-config/). QEMU does not exercise this webcam entry;
  preview and capture remain unverified by that check.
  Owner retest confirms front-camera discovery, but preview is black. Boot
  `b4212718-04d8-4706-abbf-7bb58c87a5e4` shows the diagnostic app opening camera 0, then repeated
  USB HAL SIGABRT in `HardwareJpegDecoderVaapi`: libva fails loading
  `/vendor/lib64/radeonsi_drv_video.so`, followed by `Option::unwrap()` on `None`.
  That image ships libva and Intel iHD, but no RadeonSI VA driver; its Mesa build selects only
  softpipe/Zink and RADV. Kernel logs already show `jpeg_v2_0` and a `jpeg_dec` ring.
  Owner chose hardware VA-API investigation rather than disabling the existing hardware-JPEG
  setting, then approved the [RadeonSI VA build candidate](graphics.md) and shared AMD helper.
  20 tests, actual shipping ELF imports/bytes, vendor metadata/fit, no-write repeat (39 files)
  and enforcing QEMU pass; setup screenshot inspected and VM exit confirmed.
  Google's libva/libdrm and all seven rendering libraries remain byte-identical.
  Camera-HAL namespace loading, supported JPEG profiles and actual decoding remain unverified;
  update/retest the laptop next ([build evidence](../../out/camera-vaapi/)).
  [Capture-test logs](../../out/laptop-logs/20261102-212827-m7k5rziw/current/).
  Retest with the driver still shows black preview; new boot
  `e42498e7-47ba-451f-b88a-cf9eeb462511` retains the JPEG initialization abort.
  The media probe finds the VA entry point but initialization fails. Source tracing identifies
  the inherited global Zink override as a likely conflict with the RadeonSI-only VA build.
  Approved camera-service-only clearing passes 21 tests, image read-back/metadata/fit,
  no-write repeat and enforcing QEMU (setup screen inspected, VM exited); physical retest pending
  ([details](graphics.md), [logs](../../out/laptop-logs/20261102-221612-z03h9kht/current/)).
  Latest retest (`dc40de8f-009e-4ef5-a671-9b5acb3af439`) confirms camera VA initialization
  succeeds. Preview now fails in VC effects: Vulkan DRM modifiers require 1.2 or
  `VK_KHR_image_format_list`, but strict-mode RADV reports 1.1.
  Approved native-capability build setting passes 22 tests, Mesa/image checks, no-write repeat
  (39 artifacts) and enforcing QEMU (screen inspected, VM exited). Physical Vulkan enumeration,
  desktop/app regression and camera preview/capture remain pending
  ([details](graphics.md), [logs](../../out/laptop-logs/20261102-224045-sm_8d1oi/current/)).
  Next retest (`df0b9859-30cd-4454-8299-cd2bddbcff5b`): white activation indicator, RADV 1.4
  effects context, 640x480 YUYV streaming and Vulkan import errors. A 640-byte NV12 pitch was
  inferred from the allocator but not logged
  ([logs](../../out/laptop-logs/20261102-225836-66p3d2f6/current/)).
  With NV12/NV21 pitch alignment the owner confirms preview and recording work (boot
  `7e418353-cba2-48a6-8994-c7f60114b837`). The LED also flashes under Linux; no USB reset or
  camera reopen loop was logged, but its cause is unknown
  ([details](graphics.md), [logs](../../out/laptop-logs/20261102-231851-2bm_5yev/current/)).
- Native panel backlight is under the GPU's `cardN-eDP-1`, with `max_brightness=65535`.
  Google's lights HAL accepts `backlight`, but not `amdgpu_blN`. The source patch gives only
  this model's first AMD panel that supported name; the driver/scaling algorithm is unchanged.
  Its sysfs files use the HAL's existing `sysfs_leds` permissions.
- The composer allows a modeset on every flip; on DCN 2.1 amdgpu then does a full update under
  a global lock, so with HDMI connected each display's flip waits for the other's. The
  [kernel](kernel.md) fast-flip patch keeps plain flips on the fast path.
- Google's bionic/libz use Panther Lake instructions that Zen 3 emulates in the kernel; the image
  now uses the emulator's generic builds ([os-image](os-image.md)). Expect fewer kernel traps;
  the laptop speed difference is not measured.

The regular image is [out/android/disk.img](../../out/android/disk.img), **53,430,190,080 B**
(49.8 GiB), not the separate diagnostic OS. On 2026-11-02, at the owner's request (test data), the
BUP Slim received the current image: boot files (kernel `39b8f05…`, new menu), `vendor_a` (14:47 in
[update-os.log](../../out/usb-flash-android/update-os.log)) and a 215.1 GiB `userdata` with its first
MiB blanked (14:49 in [grow-data.log](../../out/usb-flash-android/grow-data.log)), so Android
formats `/data` and runs setup again on the next boot. The stick's newest kernel before that was the
02:25 one (the pre-rename `dali/` directory held no later file), so the HDMI page-flip patch and the later menu
changes were not on it until now. A re-check found the ESP's kernel, initramfs and `BOOTX64.EFI`
hashes equal to the bundle manifest and `deploy.py` reported nothing to update; the OS partitions
are in [os-image](os-image.md). The host was not restarted and no disk but the BUP Slim was written.

| Part | Device [ID] | Driver / status |
|---|---|---|
| Display / GPU | Radeon Barcelo [1002:15e7] | `amdgpu`; usable desktop; HDMI performance reported fine, not measured |
| Keyboard | i8042 AT keyboard | `atkbd`; works |
| Touchpad | ELAN0307:00 [04f3:3282] | AMD I2C, `i2c_hid_acpi`, `hid-multitouch`; works |
| Wi-Fi | MT7922 [14c3:0616] | `mt7921e`; setup completed over Wi-Fi |
| Bluetooth | MediaTek USB [0e8d:0616] | Google's `btusb`/`btmtk`; firmware added, untested |
| Audio | HDA [1022:15e3], HDMI [1002:1637], ACP [1022:15e2] | Speakers and built-in mic work (owner report); HDMI audio not done |
| Camera / SD reader | USB [30c9:0042], [0bda:0129] | Camera works (owner report); SD reader untested |
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
  576 MiB FAT32 `GBOS-BOOT` and retains its PARTUUID. Other partitions and data stay intact.
- Boot files update through the mounted ESP with [deploy.py](../../tools/deploy.py): new files
  first, menu last, previous build retained. `make deploy-android` selects the Android bundle;
  `make deploy` is the diagnostic OS. The image's ESP uses mtools without root or mounts.
- Only the owner transfers OS partitions, with the reviewed USB by-id identity, layout checks
  and read-back. Never reflash over existing data or run recovery on the physical USB.
- Wi-Fi uses the signed mt76/MT7921E chain, Google's mac80211/cfg80211 and pinned official
  firmware. Keep `mt7921_common.disable_clc=1`; validate imports against Google's modules.
- Keep Google's HDA/audio and lights HALs. Remove the Lenovo HDA blocklist/SOF override.
  The shared [hda-audio](../../hardware/drivers/hda-audio/) selector is bounded, matches one codec
  per laptop profile (MSI ALC256 on `amd*`, Lenovo ALC233 on `intel`), logs failures and reports
  that codec only after verified renaming. SELinux permits writing only each laptop's analog
  card-ID file. No generic sysfs write grant or replacement HAL.
- The MSI patches Google's board audio directory in place. Pending owner confirmation: the Lenovo
  gets its own patched copy of Google's files, which init bind-mounts over the board directory
  (Google already allows init to mount on config directories; no new SELinux rule).
- Mixer XML uses measured ALC256 controls: mono Master and stereo Speaker/Headphone, volume
  87 = 0 dB; capture defaults off, with 23 = 0 dB when the Mic route is selected.
  Do not advertise missing HDMI/ACP PCMs as working microphones or outputs.
- Backlight naming is restricted by exact DMI vendor/model and the first panel; other machines
  retain upstream names. Drop the patch when the unchanged HAL can discover AMD backlights.
- Keep Google's power HAL, without its Panther Lake CPU masks
  ([powerhint.patch](../../hardware/msi-modern-15-b7m/vendor/powerhint.patch)). On 12 CPUs they limited apps to
  0-7, background work to 4-7, and media playback to 4-7 with no load balancing. Init's
  all-CPU cpusets stay; SocSlider and the top-app uclamp boost are kept.

## Files
- [kernel/gki.config](../../kernel/gki.config), [laptop-modules.list](../../kernel/laptop-modules.list),
  [firmware.list](../../kernel/firmware.list) — explicit drivers and firmware.
- [msi-backlight.patch](../../hardware/drivers/amdgpu/msi-backlight.patch) — narrow panel-name adaptation.
- [get_variant_audio](../../hardware/drivers/hda-audio/vendor/get_variant_audio),
  [audio-policy.patch](../../hardware/drivers/hda-audio/vendor/audio-policy.patch) — shared card
  selection and its narrow SELinux type.
- [audio-msi.rc](../../hardware/msi-modern-15-b7m/vendor/audio-msi.rc), [audio-msi.patch](../../hardware/msi-modern-15-b7m/vendor/audio-msi.patch),
  [audio-ueventd.patch](../../hardware/msi-modern-15-b7m/vendor/audio-ueventd.patch),
  [file-contexts.patch](../../hardware/msi-modern-15-b7m/vendor/file-contexts.patch) — MSI
  readiness-triggered restart, PCM/mixer configuration and scoped labels.
- [audio-lenovo.rc](../../hardware/lenovo-e50-80/vendor/audio-lenovo.rc), [audio-lenovo.patch](../../hardware/lenovo-e50-80/vendor/audio-lenovo.patch),
  [audio-policy.patch](../../hardware/lenovo-e50-80/vendor/audio-policy.patch) — Lenovo ALC233
  bind-mounted configuration and card-ID label.
- [display-lenovo.rc](../../hardware/lenovo-e50-80/system_ext/display-lenovo.rc) — Lenovo
  1920x1080 panel density 160 (it fell back to QEMU's 240, making everything 1.5x too big).
- [camera-lenovo.patch](../../hardware/lenovo-e50-80/vendor/camera-lenovo.patch) — EasyCamera
  `0bda:579c` listed as the front camera, without borrowed calibration.
- [ar9565](../../hardware/drivers/ar9565/) — Lenovo AR9565 Wi-Fi and AR3012 Bluetooth (`ath3k` firmware upload).
- [modules.patch](../../hardware/drivers/laptop-modules/vendor_dlkm/modules.patch) — codec preload/HDA unblock.
- [powerhint.patch](../../hardware/msi-modern-15-b7m/vendor/powerhint.patch) — power HAL without 8-CPU masks.
- [hardware-snapshot.sh](../../android/system_ext/hardware-snapshot.sh) — read-only physical evidence.
- [HDA tests](../../hardware/drivers/hda-audio/tests/test_audio.py),
  [AMD kernel tests](../../hardware/drivers/amdgpu/tests/test_kernel_source.py)
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
3. Follow the [Android update workflow](../build-guide.md#updating-the-existing-android-usb).
   `make update-usb JOBS=12` updates the OS partitions and boot files together, including re-signed
   modules after kernel changes. Do not select the previous or framebuffer-free menu entry.
4. Owner retest: start with low Android volume, play media, check speakers/headphones and move
   the brightness slider. Confirm density/input/Wi-Fi remain usable. Retrieve the new snapshot
   and relevant logs whether the result succeeds or fails.

### Recovering the new boot logs
First reproduce the issue using **Googlebook OS (diagnostic logs)** in GRUB. Normal boots
do not save new project logs or rotate existing captures. Saved `current`/`previous` therefore
refer to diagnostic boots, not necessarily the most recent boots; verify their identity/time.

`make laptop-logs` selects the USB, locates metadata by name
and reads current/previous logs without mounting or writing the USB. Copies belong to the normal
user; `out/laptop-logs/latest/current/` points to the newest successful retrieval. All 23 focused
log-retrieval/USB tests pass, including read-only extraction from a disposable ext4 image.
The owner ran it successfully on the USB; the retrieved [boot logs](../../out/laptop-logs/20261102-203905-md1owaep/current/)
are readable without chown. Manual recovery below remains available.
An interrupted snapshot can leave `hardware.txt.tmp` in either boot. Retrieval reports and
skips this known incomplete file after type/size checks; it never treats it as a finished
snapshot or accepts arbitrary extra files. All 10 `test_laptop_logs` tests pass in the builder,
including temporary-file safety and real ext4 read-only retrieval.

After returning to Linux, use the checked USB by-id path, not an ambiguous `/dev/sdX`. Metadata
is currently partition 17; verify the layout. Mount it `ro,noload` or read it with debugfs and
copy only `/gbos-builder-bootlog/current/` and `previous/` into a pre-created ignored evidence directory.
The files are owned by logd, so retrieval may require the owner's locally authorized sudo.

Each boot contains `boot-id`, `boot.txt`, rotated kernel/Android logs, `hardware.txt` and
`android-boot.log*`, a copy of the Android log that stops at boot completion.
The snapshot records backlight values/permissions/SELinux labels, ALSA IDs/codecs and modules.
Keep app/account logs private; share only relevant filtered excerpts.

The temporary Elantech event collector is retired at the owner's request after the working
touchpad fix. Its service, script and raw-input SELinux domain are removed; the device calibration
stays unchanged. Old `touchpad.log` files remain supported by retention and Linux retrieval.
The initial physical-device read path is now verified by the
[owner's capture](../../out/laptop-logs/20261103-202734-f4936ex7/current/touchpad.log):
11,729 events over 40.64 seconds, no `SYN_DROPPED`, typical frame spacing about 10 ms.
The monotonic-clock request is denied but realtime timestamps are recorded; capture ended
with signal 143 rather than its event/time completion marker. Large raw widths alone do not
prove palm rejection: upstream libgestures scales them by axis resolution, absent from this
first capture. The extended capability-query path remains unverified on physical hardware.
The extension passes 56 focused tests, including query failure, timeout and missing-axis
refusal. Its image build verifies the same metadata entry counts below and unchanged 4,501
Google kernel exports. Enforcing bounded QEMU again reaches setup and responds to the
accessibility tap (both screens inspected); the collector saves `status=not-present`.
A repeat preserves all 35 output/disk hashes, sizes and timestamps with no partition or boot
writes. The VM exited; [extension evidence](../../out/touchpad-axis/).
The [next capture](../../out/laptop-logs/20261104-010558-braykix7/current/touchpad.log)
verifies both position resolutions as 32 units/mm. Its single-contact widths commonly convert
to 24–34 mm: 422 of 462 frames exceed upstream's 21.2 mm single-contact palm threshold;
none reaches the default 200 pressure threshold. The owner reports fingertip motion works
longer, finger-pad motion is suppressed, multi-finger gestures still work and clicking briefly
restores motion. This supports width-based rejection, not a directly observed classifier result.
The [name-scoped IDC](../../hardware/lenovo-e50-80/vendor/ETPS_2_Elantech_Touchpad.idc) is a locally validated A/B
candidate: `gestureProp.Palm_Width = 50.0`, above both captures' single-finger widths (maximum
48.125 mm). It preserves pressure, multi-contact, edge and other gesture settings, and does
not affect differently named MSI/I2C touchpads. This is not a measured optimal calibration;
verify loaded IDC/property, sustained finger-pad movement, clicks/scroll and real palm rejection.
The candidate passes 57 focused tests, a vendor image rebuild (1,623 metadata entries and fit),
unchanged 4,501 Google exports, and a 35-output hash/size/timestamp no-write repeat.
Bounded enforcing QEMU reaches setup and responds to the accessibility tap (screens inspected);
the VM exited. QEMU does not exercise this device-name-specific calibration.
[Candidate evidence](../../out/elantech-calibration/). The owner subsequently confirms the
touchpad works after this update. This verifies usable pointer behavior by owner report,
not independent read-back of the loaded gesture property. Accidental palm rejection remains
unverified; do not describe the 50 mm threshold as an optimal measured calibration.
The initial image build verifies 3,642 system
and 238 system_ext metadata entries; both images fit. A repeat preserves all 35 published
output/disk hashes, sizes and timestamps and writes no partitions or boot files.
[Validation evidence](../../out/touchpad-diagnostic/). The disposable VM exited.

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
  `lsusb -t` on 2026-11-02 still showed it at 480M on the host's USB 2 side.
- `update-os.sh` and `grow-data.sh` end by deleting the stick's SCSI device, so Linux stops seeing it
  while it stays plugged in. Re-attach it without unplugging by rescanning its host as root:
  `echo '- - -' > /sys/class/scsi_host/host0/scan` (the host name is listed under
  `/sys/bus/usb/devices/<port>:1.0/`). Mount GBOS-BOOT for `make deploy-android` before running them.
  The tracked `make update-usb` replaces `update-os.sh` and leaves the USB attached; it requires all
  partitions unmounted and handles its own private boot mounts.
- A kernel log, boot-complete property or correctly sized PNG does not prove a usable desktop.

## Actions
- [x] Owner tests the rebuilt combined image on MSI and Lenovo — both reported working.
- [ ] Remaining physical checks — done when the owner reports
  the brightness slider visibly changing the panel, and boot/app speed with the
  generic bionic and without the firmware early console (104 s to `boot_completed` before). The
  storage check is that Settings → Storage shows roughly 215 GiB less filesystem overhead, with
  no 8 GiB jump in used space after a few minutes; no further reset is needed for this check.
  Factory-reset protection is untested; the laptop effect of RAM-only zram is unmeasured.
  Video playback is now confirmed by the owner; details are in [graphics](graphics.md).
  Retrieve the snapshot and logs either way; the snapshot now records the
  connected displays and their modes, and the CPU governor/EPP actually in effect. In
  `android-boot.log`, compare `boot_progress_enable_screen` with `sf_stop_bootanim`: a long gap
  means WindowManager waited for windows or the boot animation (QEMU waited ~30 s before `7d8e51f`).
- [ ] Headphone output — done when the owner hears media through the headphone jack.
- [ ] Bluetooth — done when the owner pairs a device and the kernel log shows `hci0` set up
  without firmware errors. Check Wi-Fi still works: both run on the same MT7922.
- [x] Lenovo Bluetooth, speaker, mic, camera and Chrome — owner-confirmed 2026-11-04.
- [ ] Confirm laptop density 160 is comfortable on the MSI and Lenovo, with QEMU still 240.
  Googlebook Settings has no display-size slider, so the image sets it per laptop.
- [ ] Diagnose the old framebuffer-free hard lockup only with a safe, evidence-based test.
- [ ] Establish whether the touchpad needs `X86_AMD_PLATFORM_DEVICE` through a separately
  agreed diagnostic A/B test; leave the working production input path unchanged.

### Ideas (not approved)
- HDMI audio, battery/suspend bring-up.
- Generalize the local OS updater only if needed; no passwordless physical-write udev rule.
- CPU frequency policy: Google's command line sets `cpufreq.default_governor=performance`; with
  amd-pstate in active mode that probably keeps the EPP at `performance` (fast, but costs battery).
  Google's powertool tries to switch non-Intel CPUs to schedutil. Decide only after the laptop
  snapshot shows the governor and EPP actually in effect.

### Capture buffer compatibility (owner-confirmed on this laptop)
- Current upstream Renoir still requires four periods, so a newer pin of this driver does not
  solve the mismatch. No capture-period setting was found in the shipped XML/HAL options;
  the visible forced-buffer option is output-only.
- The pinned kernel also contains a generic ACP stack accepting 2–8 periods and 1024-byte
  minimum periods, but its PCI selector rejects this MSI's default config flag (0). Switching
  stacks is not a configuration-only shortcut and adds more modules/machine dependencies.
- Approved [isolated patch](../../hardware/drivers/renoir-acp/renoir-capture-buffers.patch): allow two periods and
  a 1024-byte minimum in the current Renoir driver,
  retaining all maxima, allocation, rate/channel/format and DMA safeguards. The DMA ring and
  interrupt watermark already use negotiated sizes, not a hardcoded four-period layout.
  At stereo S32_LE the HAL's 20 ms period is 7680 B; its 10 ms variant is 3840 B, below today's
  4096 B minimum. 44 focused tests, image build, all 4501 Google exports/5509 prior symbol CRCs,
  signed-module metadata and image-fit checks pass. The repeat preserves 29 published file
  sizes/timestamps and writes nothing; enforcing QEMU reaches setup (screenshot inspected).
  [Evidence](../../out/renoir-buffer/). Owner confirms microphone working after the update.
  No HAL replacement or generic ACP migration; other machines and capture-quality measurements
  remain unverified.

## Handoff log
- 2026-11-04 (this commit) — Recovery now starts with reproducing under the diagnostic GRUB
  entry; normal boots preserve older captures. QEMU verifies capture/preservation and the menu;
  physical laptop behavior is not retested.
- 2026-11-04 (this commit) — Owner reports faster Lenovo Chrome launch and page loads.
  [Logs](../../out/laptop-logs/20261104-185222-9fwya0v7/current/) confirm retired touchpad capture and
  sharply lower SHA-256 trapping; CPU utilization unmeasured, MSI crypto regression still pending.
- 2026-11-04 uncommitted — Retired temporary raw touchpad capture and its dedicated policy;
  50 focused tests, image metadata checks and enforcing QEMU pass (setup screen inspected, VM exited).
  Lenovo CPU stays high after Chrome closes (owner report); fresh CPU/process evidence needed.
- 2026-11-04 (this commit) — Owner reports MSI is fine after the requested speaker, microphone
  and camera regression check on the updated combined image. Shared hda-audio regression closed;
  Lenovo fixes and smaller density were already owner-confirmed.
- 2026-11-04 (this commit) — Lenovo looked oversized at density 240 (no density setting in its
  profile, no display-size slider in Settings); added display-lenovo.rc for 160. 271 tests,
  image and QEMU (still 240) pass; owner confirms the Lenovo is now smaller.
- 2026-11-04 uncommitted — Owner confirms the Lenovo camera and Chrome work; MSI audio regression
  check still pending.
- 2026-11-04 uncommitted — Owner confirms Lenovo Bluetooth, audio and mic. Boot `20261104-052320`:
  camera enumerated but labelled external (Google's table omits `0bda:579c`), fixed by
  camera-lenovo.patch; Chrome grey traced to hasvk (see graphics). 271 tests, image and QEMU pass.
- 2026-11-04 uncommitted — Lenovo fixes from boot `20261104-010558`: `ath3k` + ar3k firmware
  (AR3012 `0cf3:3004`, ath9k btcoex), ALC233 audio via shared selector, hasvk for the camera.
  270 tests, image/kABI/module checks, QEMU setup screenshot and no-write repeat pass; untested on hardware.
- 2026-11-04 — Owner flashed the recipe image and reports MSI and Lenovo working;
  no new logs reviewed.
- 2026-11-04 uncommitted — Combined recipe image validated with 263 tests, exact baseline
  inputs/outputs, module/ABI/metadata checks and disposable QEMU. Both-laptop physical test next.
- 2026-11-04 uncommitted — Expanded MSI/Lenovo and reusable driver recipe ownership without
  changing intended runtime behavior. Validation and commit explicitly deferred.
- 2026-11-04 (this commit) — Rename audio service/readiness and diagnostic paths consistently
  with gbos-builder policy. 246 tests, image checks and enforcing saved-diagnostic QEMU pass;
  physical AMD audio/GPU and other peripheral regression remain untested.
- 2026-11-04 (this commit) — Backlight and capture fixes moved unchanged into kernel recipes.
  40 tests, exact patch/cache equality and image preservation pass; HAL/routing/calibration
  unchanged. No new physical or QEMU boot.
- 2026-11-04 (this commit) — Native config/list recipes for Lenovo ath9k and Elantech retain
  the declared Android IDC. 47 focused tests, exact expanded inputs and 37-output binary
  equality/no-write repeat pass. No new hardware/QEMU boot; existing combined image preserved.
- 2026-11-04 (this commit) — Owner confirms the Elantech palm-width candidate fixes touchpad
  use. Retain the bounded diagnostic evidence and unchanged pressure/multi-contact filters;
  accidental palm rejection remains unverified. Recipe work is a separate milestone.
- 2026-11-04 uncommitted — Axis capture verifies 32 units/mm; 422/462 single-contact
  frames exceed upstream's 21.2 mm palm threshold. Added name-scoped 50 mm IDC A/B candidate,
  preserving other filters; 57 tests, image/no-write repeat and enforcing QEMU pass. Owner retest pending.
- 2026-11-04 uncommitted — First Lenovo capture contains raw events during owner-reported
  stalls; no overflow. Added bounded axis metadata query and query-only SELinux permissions;
  56 tests, image checks, no-write repeat and enforcing QEMU pass. Physical query test remains.
- 2026-11-03 uncommitted — Owner confirms Wi-Fi and normal live-Linux Elantech behavior,
  but Android cursor stalls. Bounded touchpad-only capture passes 54 tests, metadata/fit,
  35-output no-write repeat and enforcing QEMU setup/tap; physical capture awaits owner update.
- 2026-11-03 (this commit) — Added upstream psmouse/Elantech after Wi-Fi as owner requested;
  no source patch, MSI input change or DPI change. Combined image passes 41 tests, ABI/import/
  metadata/no-write repeat and enforcing QEMU setup/input; owner Wi-Fi/touchpad retest remains.
- 2026-11-03 (this commit) — Added unchanged upstream AR9565 ath9k with Googlebook's existing
  wireless helpers (LED APIs verified). 40 tests, ABI/import/image checks, no-write repeat and
  enforcing QEMU setup/input pass. Owner Wi-Fi test pending; PS/2 touchpad remains separate.
- 2026-11-03 (this commit) — Successful Lenovo desktop logs identify unbound AR9565 Wi-Fi
  and PS/2 Elantech candidates; owner selects Wi-Fi first. Retrieval safely skips interrupted
  hardware snapshots; 10 tests pass. Drivers not yet added; original-profile freeze unresolved.
- 2026-11-02 (this commit) — Corrected current hardware status and separated the observed LED
  behavior from its unknown cause. Camera preview and recording are owner-confirmed.
- 2026-11-02 `a5befdb` — Camera works (owner-confirmed): front-facing entry, VA initialization,
  native RADV for effects and 256-byte NV12/NV21 pitches. LED also flashes under Linux.
- 2026-11-02 `a5befdb` — Camera VA initialization succeeds on laptop; effects now reject
  Vulkan dependencies under the 1.1 cap. Native-capability setting passes 22 tests, image checks,
  no-write repeat and enforcing QEMU; physical rendering/preview/capture pending, SELinux unchanged.
- 2026-11-02 `a5befdb` — VA preview still black; source trace suggests inherited Zink override.
  Approved camera-service-only clearing passes 21 tests, image/read-back/no-write repeat and
  enforcing QEMU (screen inspected); physical preview/capture remains pending.
- 2026-11-02 `a5befdb` — RadeonSI JPEG-only driver and shared AMD helper built; 20 tests,
  shipping ELF/image checks, no-write repeat and enforcing QEMU pass (screen inspected).
  No camera-HAL loading or physical preview/capture result yet; owner update/retest next.
- 2026-11-02 `a5befdb` — Owner confirms front-camera discovery, but preview is black.
  Fresh logs prove USB HAL aborts in VA JPEG initialization with the AMD video driver absent.
  Approved RadeonSI VA build candidate added; validation and physical capture pending.
- 2026-11-02 `a5befdb` — Fresh logs show camera ID 2 advertised as external, not missing
  UVC support. Scoped front-facing candidate passes 13 tests, image metadata/read-back/fit,
  no-write repeat and enforcing QEMU; physical HAL acceptance/visibility/preview/capture pending.
- 2026-11-02 `a8c655f` — Owner confirms microphone works after the Renoir buffer update.
  Closed the built-in capture task; no new capture logs, quality measurements or separate
  speaker/headset regression result supplied. HDMI audio and camera remain separate work.
- 2026-11-02 (this commit) — Renoir-specific buffer candidate passes 44 tests, ABI/image checks,
  no-write repeat and enforcing QEMU; screen inspected. Separate from generic ACP migration;
  microphone-slider/no-input remains the latest physical result until the owner updates/retests.
- 2026-11-02 (this commit) — Owner sees the microphone slider but diagnostic app detects no input;
  new logs confirm correct ACP/format but incompatible HAL period count (2 vs driver's 4).
  `make laptop-logs` passes 23 tests and owner USB retrieval; no USB writes or recording success.
- 2026-11-02 (this commit) — Laptop ACP PCM confirmed; added InternalMic route on named card `acp`.
  31 tests, image metadata/read-back/fit, no-write repeat and enforcing QEMU pass; analog routes
  unchanged. Owner update and physical recording test pending.
- 2026-11-02 (this commit) — Driver-only Renoir ACP image passes tests/build/kABI and enforcing
  QEMU; unchanged repeat writes nothing. Laptop PCM check pending; speaker/headset routes unchanged.
  HDMI audio/camera remain; camera is already discovered by Google's USB HAL.
- 2026-11-02 (this commit) — Owner confirms video fixed and the previously failing game,
  another native app and Hearthstone working with optional Berberis. Normal boot remains Houdini;
  new laptop logs and broader app compatibility remain unverified.
- 2026-11-02 (this commit) — Owner's video retest crashes the desktop. Reused their earlier gbos
  YV12 findings as Mesa/minigbm source patches. 131 tests, vendor rebuild/ABI checks and enforcing
  QEMU pass; patches not deployed and new crash log not yet retrieved.
- 2026-11-02 (this commit) — Main USB update workflow is now `make update-usb JOBS=12`: select
  the disk, confirm by serial, update OS and boot files without touching data. 129 fixture tests
  pass; first physical use of the new tool is pending. No USB write made.
- 2026-11-02 (this commit) — Owner reports HDMI fine; Vulkan HWUI has no noticeable speed benefit.
  Retrieved both boots' logs read-only: software codecs crash on Mesa's sandboxed affinity query.
  Vendor policy fix built and QEMU-checked, not written to the USB; laptop playback retest pending.
- 2026-11-02 (this commit) — Wrote the stick at the owner's request (test data): boot files (kernel
  `39b8f05…`; its newest had been the 02:25 one), `vendor_a` (zram writeback off) and `userdata`
  32 → 215.1 GiB, blanked. Re-checks found nothing more to write. Not booted yet.
- 2026-11-02 (this commit) — Owner-run `grow-data.sh` can enlarge /data into the stick's free space
  (userdata can reach about 215 GiB), erasing it ([os-image](os-image.md)). Tested on file copies
  and in QEMU only; the owner decides whether to run it.
- 2026-11-02 (this commit) — Disabled mmd's zram writeback in the vendor `build.prop` ([os-image](os-image.md)),
  which stops an 8 GiB file being created in /data each boot. QEMU-verified only; the owner
  deploys it with `update-os.sh` (vendor only).
- 2026-11-02 (this commit) — Installed the official MT7922 Bluetooth RAM code the `95b3bf6` boot
  lacked. Vendor image holds the archive's exact bytes; QEMU has no Bluetooth, so it is untested.
- 2026-11-02 `e51523d` — Snapshot now records DRM connectors and cpufreq policies, so the next
  retest shows HDMI state and the real governor/EPP. Verified in enforcing QEMU only.
- 2026-11-02 `3f49946` — Power HAL CPU masks removed: with 12 vCPUs, QEMU cpusets went from
  0-7/4-7 to 0-11 everywhere and the 500 ms xe-IRQ write retries stopped; `qemu-check` passed.
  `9663a21` removed the 10 s TPM wait. Laptop effect not measured.
- 2026-11-02 `6d0d663`–`9663a21` — Owner confirmed sound on `95b3bf6`, reported HDMI halving the
  frame rate. HDMI flip patch, generic bionic/libz and polling fixes verified in QEMU only.
  Next: owner updates boot files and OS partitions and retests.
- 2026-11-02 `95b3bf6` — ALC256 routing/mixer and MSI-only backlight naming built; scoped
  enforcing audio selection and a real 1 kHz QEMU signal verified with a test-only mixer.
  No physical writes/reboot. Next: owner updates both boot and OS files and retests hardware.
- 2026-11-02 `ec5d360` — Density 160, HDA unblock and read-only snapshot built and QEMU-checked.
  Owner subsequently booted it; sound and brightness still fail.
- 2026-11-02 `ab9d9c5` — Owner updated the USB and completed setup over Wi-Fi; input works.
  UI feels fast, not benchmarked. Sound and brightness are the remaining reported failures.
- 2026-11-02 `3f7ce26` — Source-level framebuffer handoff reached physical setup with input.
  Earlier framebuffer-free test panicked; keep the normal entry and EFI safeguard.
