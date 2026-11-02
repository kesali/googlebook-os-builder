# Laptop hardware

**Status:** partial — the laptop completes setup over Wi-Fi with a working touchpad; sound and
screen brightness do not work.
**Last verified:** 2026-11-02 — with the Wi-Fi/density build (`ab9d9c5`) the owner booted the
normal entry, joined Wi-Fi and completed initial setup; the touchpad works. The owner finds app
launches and graphics faster than Churro and gbos-x86 (impression, not measured). Sound and the
brightness setting do not work. Density 180 and the keyboard were not explicitly confirmed.
Earlier that day the handoff build showed setup with an oversized UI and no Wi-Fi.
Earlier that day: the new kernel hands simpledrm card0 to virtio in an offline
disposable UEFI boot; [setup](../../out/fb2/android-uefi-console-g0b93ipe/before-input.png)
responded to a [mouse click](../../out/fb2/android-uefi-console-g0b93ipe/after-input.png).
EFI pstore was disabled and the NVMe decoy stayed unchanged. The owner updated the USB boot
files; [read-back matched](../../out/framebuffer-handoff-evidence/usb-update-readback.txt)
and the owner reported that a repeat update wrote nothing.
2026-11-01 — the owner's framebuffer-free test hard-locked. EFI crash records
show an RCU stall before a duplicate `i2c_hid_acpi` load failed; the cause remains unknown.
The panic wrote 21 EFI crash records.
Earlier, the owner's USB retest left kernel logs on screen. Recovered
[kernel logs](../../out/laptop-boot-2026-11-01/physical-boot-logs/recovered/kernel.log.2)
show amdgpu on minor 1; [Android logs](../../out/laptop-boot-2026-11-01/physical-boot-logs/recovered/android.log.7)
show repeated invalid present fences. The framebuffer-free GRUB entry passed a disposable QEMU
shell check and was verified on the updated USB before the laptop test.
Earlier, 19 focused tests and three disposable UEFI boots verified the diagnostic candidate:
enforcing native collectors, real logs and two-boot retention
([results](../../out/bootlog-validation/persistence-checked.log),
[setup screenshot](../../out/bootlog-validation/rotation-checked/boot-3/screen.png) inspected).
Before that: the stick's `/metadata`, read-only after the laptop boots
([evidence](../../out/laptop-boot-2026-11-01/metadata-evidence.txt)), shows Android's init, apexd
and aconfigd ran. A QEMU VM with its GPU at the laptop's PCI path reproduced the loop and reaches
setup with the fix ([before/after](../../out/laptop-boot-2026-11-01/qemu-repro/)). `make test` and
`make qemu-check JOBS=12` pass ([screen](../../out/qemu/screen.png) inspected). Only `vendor_a`
was rewritten on the stick; layout checks and read-back pass ([log](../../out/usb-flash-android/update-os.log)).
Earlier that day: the image was written to the BUP Slim; a full read-back matched
and the partition table, GPT entries and ESP were re-checked after moving the backup GPT
([flash log](../../out/usb-flash-android/flash.log)).
Before that: `make test minigbm-check` (59 Python tests plus GBM checks),
`make android-uefi-check JOBS=12`: the
[DRM log](../../out/android-uefi-console-p_3gmgei/early-screen.png) and, in a separate display
configuration, [Android setup](../../out/android-uefi-graphics-pgfv692u/screen.png) were inspected.
Both guests found the USB disk; neither enumerated or changed the NVMe decoy. The source disk's
bytes and mtime stayed unchanged. A separate disposable direct-kernel run selected softpipe
without a graphics boot property; its virtual mouse reached the
[low-battery dialog](../../out/overnight/direct/mouse-click.png). Keyboard navigation remains
unconfirmed: Tab/Enter did not dismiss it. Earlier M1 kernel/ESP checks are in `out/m1-validation/`.
2026-10-31 — diagnostic USB only: owner
confirmed boot/shutdown; [hardware report](../../out/laptop-boot-2026-10-31/hardware.txt) and
[kernel log](../../out/laptop-boot-2026-10-31/kernel.log) reviewed. The BUP Slim was measured
read-only: [drive notes](../../out/laptop-boot-2026-10-31/usb-drive.txt).

## Goal
Run the same Googlebook OS on the **MSI Modern 15 B7M** (Ryzen 5 7530U, Radeon Vega graphics,
MT7922 Wi-Fi/Bluetooth, ELAN touchpad, HDA/ACP audio), adding drivers one at a time and
updating the USB incrementally instead of reflashing.

## Current state
The base image is [out/android/disk.img](../../out/android/disk.img), 53,430,190,080 B
(49.8 GiB; use a 64 GB or larger USB). It is not the 514 MiB diagnostic image.
It contains the previous kernel/OS, UEFI boot files, signed AMD modules, 23 official runtime firmware
blobs and the RADV/Zink/minigbm graphics stack. On 2026-11-01 it was written unchanged to the
BUP Slim by a one-time checked sudo script ([flash.sh](../../out/usb-flash-android/flash.sh)):
35 MB/s write, then a full read-back that matched. Then `sfdisk --relocate gpt-bak-std` moved the
backup GPT to the disk end; at that point the partition table (same PARTUUIDs), GPT entries and
ESP bytes matched and `fsck.fat` was clean. The stick also carries the disk's QEMU userdata
(6.2 GiB in use).
The owner booted it twice: the screen slowly repeated the same init lines. Google labels the GPU's
sysfs identification files (`vendor`, `device`, …) only at Intel's `00:02.0`; our patch labelled
only `uevent` at the laptop's `00:08.1/03:00.0`. libdrm skipped the GPU, Mesa found no DRM device
and SurfaceFlinger aborted; in QEMU at the same path init restarted it, and killed zygote, 118
times in 10 minutes. [file-contexts.patch](../../android/vendor/file-contexts.patch) now labels
Google's full set; [update-os.sh](../../out/usb-flash-android/update-os.sh) put it on the stick.
The owner then updated the OS partitions and retested: Android reached boot-complete, but the
screen stayed on the kernel log. Simpledrm took minor 0 before amdgpu registered as minor 1.
The composer may have missed the GPU if card0 was absent; its startup messages rotated out, so
this remains a hypothesis. The owner confirmed that their Churro build booted this laptop with
AMD and touchpad working; its framebuffer handoff is now built and QEMU-verified, not yet tested
on the laptop.
The opt-in GRUB entry tests the hypothesis without changing the normal default;
the owner updated the USB menu, and read-back confirmed the new menu and original backup. That
test later hard-locked during early-init; no usable display or new metadata logs were recovered.
The first diagnostic boot passed both instruction-emulation tests and registered the internal
keyboard and ELAN0307 touchpad with `hid-multitouch`. Pointer motion/gestures were not tested.
The same boot drew the screen through simpledrm at 0.50 s (`simple-framebuffer.0`, 128x48 text).
The Android kernel has the touchpad/simpledrm/drm_log built-ins and modular amdgpu
([gki.config](../../kernel/gki.config)). All 4501 Google exports keep their CRCs, and Google's ABI
whitelist and helper modules remain unchanged. AMD module initialization is verified, but a
usable display and the other laptop devices remain unverified.
The USB for Android is the BUP Slim (232.9 GiB). It linked at USB 2.0 (480 Mb/s, 39 MB/s
sequential, 0.34 ms random reads); Linux calls it rotational, but the media type is unknown.
`out/android/disk.img` has the USB's layout: Google's all-zero EFI-SYSTEM (64 MiB) and `KERN-A`
(512 MiB) are one 576 MiB FAT32 EFI-SYSTEM (`DALI-BOOT`, same PARTUUID; see [os-image.md](os-image.md)).
`make android-boot` fills it with the laptop's boot files: GRUB, the GKI kernel, the initrd and a
menu ([android-menu.cfg](../../boot/android-menu.cfg)) holding Android's command line plus
`panic=0 earlycon=efifb printk.devkmsg=on console=drm_log initcall_blacklist=nvme_init`.
The prior image's boot files matched their build hashes and passed `fsck.vfat`. QEMU's
direct-kernel boot ignores the partition and still reaches the setup welcome page.
OVMF reads the ESP and GRUB loads the GKI kernel and initrd from it. Android mounts the USB's
partitions (`sda`, EFI-SYSTEM at `sda12`) with SELinux enforcing; `nvme_init` hides the decoy.
The test uses `virtio-vga` to verify simpledrm/drm_log, and `virtio-gpu-pci` without a firmware
framebuffer to verify the setup UI. Before the new handoff, both active together showed only a
status bar. The new kernel's combined offline QEMU boot reaches setup and accepts a mouse click.
The USB now has the new kernel; the original disk retains the previous kernel. Not verified: AMD
handoff/rendering, UAS boot, physical input or a usable Android screen on the laptop. Wi-Fi,
Bluetooth, audio and suspend have not been brought up.
The devices below were read from this laptop running a desktop Linux (`lspci -nnk`, `lsusb`,
`/proc/bus/input/devices`).

| Part | Device [ID] | Linux driver | Needed for Android |
|---|---|---|---|
| Display / GPU | Radeon "Barcelo" [1002:15e7] | `amdgpu` | Candidate includes amdgpu, RADV/Zink, ANGLE and Mesa-backed minigbm |
| Keyboard | i8042 "AT Translated Set 2" | `atkbd` | Built into GKI already |
| Touchpad | ELAN0307:00 [04F3:3282] on I2C controller AMDI0010:03 | `i2c_hid_acpi` + `hid-multitouch` | AMD I2C, GPIO and I2C HID drivers (see Pitfalls) |
| Wi-Fi | MediaTek MT7922 [14c3:0616] | `mt7921e` | Module + firmware |
| Bluetooth | MediaTek USB [0e8d:0616] | `btusb` | Module + firmware |
| Audio | HDA [1022:15e3], HDMI [1002:1637], ACP [1022:15e2] | `snd_hda_intel`, `snd_rn_pci_acp3x` | HDA + AMD ACP |
| USB | xHCI [1022:1639] ×2 | `xhci_hcd` | Built into GKI already |
| Camera, SD reader | USB [30c9:0042], [0bda:0129] | `uvcvideo`, `rtsx_usb` | Later |
| Storage | Samsung PM9C1a NVMe [144d:a80d] | `nvme` | Boot from USB first; internal NVMe stays untouched |

## Decisions
- QEMU boots to the setup screen, which is enough: the laptop is the focus and QEMU polish is
  parked. No installer and no dual boot for now.
- Milestone M1 (agreed by the owner, 2026-10-31): the kernel log, keyboard and touchpad on the
  laptop. The owner's subsequent overnight request (2026-11-01) extends this to an Android UI
  test candidate (M2/M3); simpledrm alone is not the Android rendering path.
- Build only the missing AMD modules, sign with the rebuilt kernel's trusted key, and retain
  Google's helpers. Use official linux-firmware unchanged. No symbol-whitelist relaxation.
- The menu selects AMD for `1002:15e7`, softpipe otherwise. AMD uses Google's ANGLE, RADV
  RenderEngine, GL HWUI and Mesa GBM/Zink; keep QEMU's proven software path. See [graphics.md](graphics.md).
- USB layout: Google's whole GPT, as in `out/android/disk.img`. Android finds its disk by the
  PARTUUID of EFI-SYSTEM (`androidboot.boot_part_uuid`) and its partitions by name. EFI-SYSTEM
  grows from 64 to 576 MiB by absorbing the blank `KERN-A` beside it and keeps its PARTUUID.
  GRUB, kernel, initrd and menu live there and update like the diagnostic USB
  ([deploy.py](../../tools/deploy.py): new files first, the menu last, previous build kept).
  This replaces the diagnostic image on the stick; flash it again only for a hardware check.
  QEMU's disk and the USB are the same image (owner's choice, 2026-11-01).
- Two ways to fill the ESP, one menu. `make android-boot` writes the disk image's ESP with mtools
  (no root, no mount): it replaces `EFI/` and `dali/` as a whole, so the image never carries an
  old build, and it refuses any partition not labelled `DALI-BOOT`. A mounted stick gets
  [deploy.py](../../tools/deploy.py)'s incremental update with the previous build kept (the
  `android` bundle kind, tested on a temporary directory; no make target yet).
- The internal NVMe stays invisible to Android on the laptop: its GRUB entry adds
  `initcall_blacklist=nvme_init` (Google's kernel has NVMe built in). QEMU's direct-kernel boot
  uses an NVMe disk and keeps it. The UEFI test must show a decoy NVMe disk is never enumerated
  and stays byte-identical (owner agreed, 2026-11-01).
- Explicitly select `console=drm_log`: Google's built-in `console=ttynull` otherwise suppresses
  the screen log even when simpledrm registers. This console setting needs no policy change;
  the separate source patch handles the proposed framebuffer handoff.
- Use the Churro-based PCI framebuffer handoff without changing touchpad drivers, the NVMe
  blacklist or the EFI safeguard; validate it before an owner-approved USB update and laptop boot.
- Updates: boot files go to the mounted ESP without sudo. OS partitions are raw writes to the
  stick, only with the owner's explicit approval, a checked by-id USB target and a sudo
  password typed locally (VS Code task). No udev rule.
- M1 drivers are built into the kernel: `X86_AMD_PLATFORM_DEVICE` and `PINCTRL_AMD` cannot be
  modules, and the simpledrm display with `DRM_CLIENT_LOG` must run before userspace to show the
  log. The touchpad's I2C drivers stay built in, as proven in the diagnostic kernel. Built-in
  code needs no exports, so Google's ABI list and CRCs should stay intact (`make gki` checks).
  Larger drivers (`amdgpu`, Wi-Fi, audio) stay modules (see [kernel.md](kernel.md)).
- Firmware is never written: SPI-flash and TPM drivers stay blacklisted.
- Wi-Fi: only the mt76/MT7921E chain is built and signed; Google's cfg80211 and mac80211
  stay (they export everything mt76 needs). `laptop-modules.sh` runs `depmod -e -E` against Google's real
  vendor_dlkm/system_dlkm modules, so a missing export or CRC mismatch fails the build. MT7922
  firmware comes from the pinned linux-firmware; the laptop menu adds `mt7921_common.disable_clc=1`.
- Density 180 on the laptop only: the AMD profile sets `qemu.sf.lcd_density`, which Google's
  SurfaceFlinger and zygote read before `ro.sf.lcd_density` (240, kept for QEMU).

## Files
- [kernel/gki.config](../../kernel/gki.config) — where the M1 built-ins and later driver modules are listed.
- [kernel/laptop-modules.list](../../kernel/laptop-modules.list), [kernel/msi-firmware.list](../../kernel/msi-firmware.list) — exact modules and firmware shipped.
- [scripts/laptop-modules.sh](../../scripts/laptop-modules.sh), [scripts/firmware.sh](../../scripts/firmware.sh) — signed-module and official-firmware publication.
- [scripts/android-disk.sh](../../scripts/android-disk.sh) — Google's disk layout, which the USB copies.
- [boot/android-menu.cfg](../../boot/android-menu.cfg), [scripts/android-boot.sh](../../scripts/android-boot.sh) — the laptop's GRUB menu; writes the boot files into the disk's ESP.
- [tools/deploy.py](../../tools/deploy.py) (diagnostic and android bundle kinds), [tools/android_sync.py](../../tools/android_sync.py) — boot-file and OS-partition updaters.
- [tools/android_uefi_test.py](../../tools/android_uefi_test.py), [tests/test_android_uefi.py](../../tests/test_android_uefi.py) — disposable UEFI boots and their safety/evidence checks.
- [android/cmdline.txt](../../android/cmdline.txt) — Intel arguments already removed.
- Reference ports (not in Git): `reference/project-churro-msi-modern-15-B7M`, `reference/gbos-x86-msi-modern-15-B7M`.

## Verify
M1, in this order:
1. `make test`, `make gki JOBS=12` (config, ABI and certificate checks), then `make qemu-check JOBS=12`.
   Run for the built-ins on 2026-11-01: all pass; QEMU's `screen.png` shows the setup language list.
   Run again on the recreated disk with the FAT32 EFI-SYSTEM: passes; `screen.png` shows the setup welcome page.
   Run again with the boot files in it: passes, same screen.
   `make android-boot` twice: the first run writes, the second prints "up to date" and leaves the
   disk's mtime alone. Check the files with `mdir -/ -i out/android/disk.img@@<start*512> ::`
   (start sector in `out/android/disk.img.layout.txt`).
2. `make android-uefi-check JOBS=12`: two disposable copies boot through OVMF/GRUB as USB storage,
   each beside a writable NVMe decoy. The console run requires simpledrm/drm_log and an enforcing
   Android shell; the graphical run reuses the full Android smoke checks without a firmware
   framebuffer. Both require the USB partition path, no NVMe enumeration and unchanged decoy
   hashes. Run on 2026-11-01; inspect the screenshots linked above. Not a graphics-handoff test.
3. Write the USB with the owner's approval; read it back and check the ESP files read-only.
   Run on 2026-11-01: passes ([flash log](../../out/usb-flash-android/flash.log)).
4. Boot the laptop. Earlier attempts reached userspace but failed; the post-fix retest still
   hangs according to the owner. New evidence needs saved logs and a screen photo in `out/`.
   A kernel log does not prove "boots": that requires a usable Android screen and input.

### Recovering the new boot logs

The candidate passed review and QEMU validation. The owner updates and boots the USB,
then returns to Linux. Diagnostics change `system_a`, `vendor_a` and `system_ext_a`;
a boot-file-only or vendor-only update is insufficient. The existing one-time
[OS updater](../../out/usb-flash-android/update-os.sh) covers these ranges, checks layout and
read-back, and preserves data; running it remains an owner-authorized physical write,
not an assistant action. Do not reflash the entire image over existing Android data.

Mount **that USB's metadata partition** read-only with
`ro,noload`, using its checked USB by-id path, not an ambiguous partition label. It is currently
partition 17; verify the actual layout rather than guessing `/dev/sdX`.
Copy only `dali-bootlog/current/` and `previous/` into an ignored laptop evidence directory;
their logd ownership means the copy may need locally authorized sudo. If an unclean shutdown
leaves stale inodes, ask the owner before making a private temporary RAM copy of metadata
(which contains unrelated security state). Replay the journal on that regular copy only,
extract the logs and remove the copy; never run recovery on the USB. Check that swap is not
disk-backed before using tmpfs.

Each directory contains `boot-id`, `boot.txt`, `kernel.log` and `android.log`, plus up to
seven numbered archives per stream (largest archive number is oldest).
Logs can contain private app/account information: inspect locally and share only the relevant
filtered excerpts. Preparation/collector errors are reported to the kernel log; a hang before
metadata/logd becomes available may leave no saved files, so also photograph the screen.
The assistant never writes physical devices; image transfer and laptop boot are owner steps.
The physical retest required journal replay on an owner-approved RAM copy before extraction.

## Pitfalls
- Googlebook userspace uses instructions this CPU lacks; the kernel's emulator patch is required (see [kernel.md](kernel.md)).
- The touchpad needs `X86_AMD_PLATFORM_DEVICE` (built-in only: it sets the AMD I2C clock),
  `PINCTRL_AMD`, `I2C_DESIGNWARE_PLATFORM` and `I2C_HID_ACPI`; Google's GKI config has none of them.
  The diagnostic USB enables all of them and registers the touchpad; motion/gestures and the
  comparison without `X86_AMD_PLATFORM_DEVICE` are still untested.
  The reference port never got this touchpad working.
- Google's kernel config has no `DRM_SIMPLEDRM`, `FB`, `VT` or `amdgpu`, so nothing would draw the
  kernel log once the early console (`earlycon=efifb`) ends; the M1 built-ins add that (expected,
  not yet seen on the laptop).
- The initrd names EFI-SYSTEM's PARTUUID ([android-initrd.sh](../../scripts/android-initrd.sh));
  any GPT written to the USB must keep it, or first-stage init cannot find the disk.
- Merge only `KERN-A`: `ROOT-B` holds a 17 MB EROFS and `ota_recovery_a` a nested GPT.
- Plug the BUP Slim into a SuperSpeed port with a USB 3 cable; `lsusb -t` must show 5000M or
  10000M, not 480M.
- Debian's OVMF did not discover QEMU's UAS-only device (it dropped to its shell); the test uses
  USB bulk-only transport. This does not establish how the BUP Slim behaves under laptop firmware.
- Keep QEMU's GPU at PCI `00:02.0`: Google's `sysfs_gpu` label covers that path. At `00:03.0`,
  SurfaceFlinger cannot read its `uevent` and Mesa reports no DRM device. Fix the QEMU address,
  not SELinux policy; the decoy is explicitly at `00:03.0`. The laptop's own path must label every
  file libdrm reads (`uevent`, `vendor`, `device`, `subsystem_*`), not just `uevent`.
- The same init lines repeating on the drm_log screen mean a crash loop: drm_log draws only while
  no process holds DRM master, wraps instead of scrolling and replays when amdgpu registers.
  Without root, `udisksctl mount -b /dev/sdX17 -o ro,noload` shows what reached `/metadata`.
  QEMU root ports at `07.0`, `08.0` and `08.1` put the GPU at the laptop's path
  ([script](../../out/laptop-boot-2026-11-01/qemu-repro/qemu-laptop-gpu.sh)).
- SetupWizard's Next button shows a low-battery dialog in the USB VM (no battery is emulated).
  Setup completion is not part of this test. An extra input probe then lost serial responses
  after a 180-second pause ([log](../../out/m1-validation/b3-input-probe.log)); the passing
  bounded boot checks do not establish longer-running stability.
- The serial shell is UID 2000, not root: modprobe and raw input-event reads are inaccessible.
  The AMD module tree's 1,585 import CRCs were checked statically against actual Google helpers
  ([evidence](../../out/overnight/module-crcs.log)); runtime AMD loading remains unverified.

## Actions
Next, with this spec updated after the physical test:
- [x] Validate the framebuffer handoff on the laptop — setup screen and touchpad confirmed by the owner.
- [ ] Wi-Fi (MT7922) so setup can finish — done when the laptop joins a network in setup.
- [ ] Laptop density 180 (owner's Churro setting), QEMU unchanged — done when the owner confirms
  normal-sized UI on the laptop.
- [ ] Audio (ALC256 over HDA) — after Wi-Fi; done when the owner hears sound.
- [ ] First laptop Android boot — done when an inspected photo shows usable setup and the
  keyboard/touchpad work. Setup and touchpad are confirmed; keyboard not yet checked.
- [ ] Diagnose the framebuffer-free hard lockup — done when the cause and a safe next test are
  established. Keep NVMe hidden and networking, audio and speculative performance changes out
  of this repair.
- [ ] Find out if the touchpad needs `X86_AMD_PLATFORM_DEVICE` — done when the diagnostic USB
  has been booted with and without it (`make deploy` after removing it from
  [msi-diagnostic.config](../../kernel/msi-diagnostic.config)) and the touchpad result is recorded here.

### Ideas (not approved)
- M4: Wi-Fi (`mt7921e`), Bluetooth (`btusb`), audio (HDA/ACP), battery and suspend.
- A boot logger (an `rdinit` hook writing to the ESP) if photos of the screen are not enough.
- A udev rule for passwordless OS-partition writes to this one USB.
- A make target from [update-os.sh](../../out/usb-flash-android/update-os.sh): writes only the
  OS ranges that differ, after checking the stick's GPT and super metadata match the image.

## Handoff log
- 2026-11-02 `uncommitted` — Vulkan HWUI draft reverted (GL HWUI kept). Wi-Fi and density 180
  built: `make test` passed, `make gki` kABI clean, laptop-module check passed against Google's
  mac80211 (`mt7921-common` also needs `hwmon`, added to `modules.patch`), MT7922 firmware and
  the density setprop are in the image, and `make qemu-check` passed with the setup screen
  inspected. Not yet tested on the laptop: Wi-Fi, density 180. Next: owner updates the USB.
- 2026-11-02 `uncommitted` — Owner's laptop boot shows setup with a working touchpad; UI too
  large, no sound, no Wi-Fi. Owner chose Wi-Fi and laptop-only density 180 next, audio after.
  MT7922 modules/firmware/CLC workaround and the density setting are drafted but not built or
  tested; the build may show Google's trimmed mac80211 lacks exports mt76 needs.
- 2026-11-02 `uncommitted` — Owner installed the guarded handoff on USB; boot files read back
  correctly and the owner reports a no-op repeat. Laptop AMD and input remain unverified.
- 2026-11-02 `uncommitted` — EFI pstore safeguard passes offline UEFI control and both entries.
  The saved previous build may remain unsafe.
- 2026-11-01 `uncommitted` — The owner's retest reached boot-complete but stayed on logs.
  Recovered logs show amdgpu minor 1 and invalid present fences. The framebuffer-free GRUB
  experiment passes the QEMU shell check and USB read-back; laptop test panicked.
- 2026-11-01 `uncommitted` — Owner reports the laptop still hangs after the GPU-label fix.
  Native diagnostics pass 19 focused tests and three UEFI boots, with inspected setup and
  Linux-readable logs. Next: owner updates OS partitions and returns new laptop logs/photo.
- 2026-11-01 (this commit) — Laptop boots crash-looped SurfaceFlinger (GPU sysfs files unlabelled);
  reproduced and fixed in QEMU at the laptop's PCI path. With the owner's sudo, only `vendor_a`
  was rewritten on the stick (read-back matches). Next: the owner's retest, photo of the result.
- 2026-11-01 `21277da` — With the owner's approval, wrote the AMD candidate to the BUP Slim
  (by-id, USB, unmounted and locked); full read-back, GPT re-check and `fsck.fat` pass; ejected.
  Next: the owner's first laptop boot (photo of setup or of the last log screen).
- 2026-11-01 `54771be` — Prepared the owner's overnight AMD candidate: signed modules,
  official firmware, RADV/Zink/ANGLE and ABI-checked minigbm. UEFI log/UI checks pass, data is
  preserved and no-op takes 16 s. No physical writes; AMD display/input await the owner.
- 2026-11-01 `810ad08` — UEFI USB checks pass in separate log/UI configurations; screenshots
  inspected, NVMe decoys hidden and unchanged. Added `console=drm_log`; GPU fixed at PCI 00:02.0.
  Graphics handoff and laptop remain unverified. Next: prepare USB deployment.
- 2026-11-01 `deee56b` — `make android-boot` puts GRUB, the GKI kernel, initrd and the laptop menu in
  the disk's ESP (mtools, no root); checked by `mdir`, `fsck.vfat`, hashes, a no-op rerun and
  unchanged neighbours. Not run under UEFI yet. Next: the UEFI boot test in QEMU.
- 2026-11-01 `4811074` — The disk's EFI-SYSTEM is now a 576 MiB FAT32 (blank `KERN-A` absorbed),
  checked and booted in QEMU. The owner chose one disk for QEMU and the USB, and hiding the NVMe on
  the laptop. Next: boot files in the ESP, then the UEFI test.
- 2026-11-01 `a9ca093` — M1 built-ins added to the Android kernel and checked: config, ABI (4501
  exports unchanged) and QEMU boot pass. Next: the Android USB image, tested in QEMU through UEFI.
- 2026-10-31 `9c78a5d` — Owner agreed the first laptop boot plan: Google's GPT with a 576 MiB
  EFI-SYSTEM, boot files via the mounted ESP, OS partitions via a sudo task, M1 first.
  BUP Slim measured at USB 2.0. Plan and QEMU spec updated; no code changes.
- 2026-10-31 `af0f7b6` — First diagnostic boot/shutdown confirmed by the owner; logs show
  ELAN0307 I2C HID/multitouch registration and passing instruction tests. No Android boot or
  touchpad motion test yet; no driver/config changes made.
- 2026-10-31 `81c4536` — Device IDs and drivers recorded from the laptop's desktop Linux;
  touchpad drivers added to the diagnostic kernel. Not yet booted on the laptop.
- 2026-10-31 — Spec created; no laptop Android work yet.
