# Laptop hardware

**Status:** partial — AMD test image ready; Android has not been booted on the MSI laptop.
**Last verified:** 2026-11-01 — `make test minigbm-check` (59 Python tests plus GBM checks),
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
The laptop candidate is [out/android/disk.img](../../out/android/disk.img), 53,430,190,080 B
(49.8 GiB; use a 64 GB or larger USB). It is not the 514 MiB diagnostic image.
It contains the shared kernel/OS, UEFI boot files, signed AMD modules, 23 official runtime firmware
blobs and the RADV/Zink/minigbm graphics stack. It has not been written to a physical USB.
The first diagnostic boot passed both instruction-emulation tests and registered the internal
keyboard and ELAN0307 touchpad with `hid-multitouch`. Pointer motion/gestures were not tested.
The same boot drew the screen through simpledrm at 0.50 s (`simple-framebuffer.0`, 128x48 text).
The Android kernel has the touchpad/simpledrm/drm_log built-ins and modular amdgpu
([gki.config](../../kernel/gki.config)). All 4501 Google exports keep their CRCs, and Google's ABI
whitelist and helper modules remain unchanged. No physical-laptop driver is verified.
The USB for Android is the BUP Slim (232.9 GiB). It linked at USB 2.0 (480 Mb/s, 39 MB/s
sequential, 0.34 ms random reads); Linux calls it rotational, but the media type is unknown.
`out/android/disk.img` has the USB's layout: Google's all-zero EFI-SYSTEM (64 MiB) and `KERN-A`
(512 MiB) are one 576 MiB FAT32 EFI-SYSTEM (`DALI-BOOT`, same PARTUUID; see [os-image.md](os-image.md)).
`make android-boot` fills it with the laptop's boot files: GRUB, the GKI kernel, the initrd and a
menu ([android-menu.cfg](../../boot/android-menu.cfg)) holding Android's command line plus
`panic=0 earlycon=efifb printk.devkmsg=on console=drm_log initcall_blacklist=nvme_init`. The files match the build's
hashes and `fsck.vfat` is clean. QEMU's direct-kernel boot ignores the partition and still reaches
the setup welcome page.
OVMF reads the ESP and GRUB loads the GKI kernel and initrd from it. Android mounts the USB's
partitions (`sda`, EFI-SYSTEM at `sda12`) with SELinux enforcing; `nvme_init` hides the decoy.
The test uses `virtio-vga` to verify simpledrm/drm_log, and `virtio-gpu-pci` without a firmware
framebuffer to verify the setup UI. With both simpledrm and virtio active, the visible virtio
screen had only the status bar, not a usable setup UI; the two-pass check does not fix that.
Not verified: AMD device binding/rendering, a framebuffer-to-GPU handoff, UAS boot, physical input
or any Android boot on the laptop. Wi-Fi, Bluetooth, audio and suspend have not been brought up.
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
  the screen log even when simpledrm registers. No kernel patch or policy change is needed.
- Updates: boot files go to the mounted ESP without sudo. OS partitions are raw writes to the
  stick, only with the owner's explicit approval, a checked by-id USB target and a sudo
  password typed locally (VS Code task). No udev rule.
- M1 drivers are built into the kernel: `X86_AMD_PLATFORM_DEVICE` and `PINCTRL_AMD` cannot be
  modules, and the simpledrm display with `DRM_CLIENT_LOG` must run before userspace to show the
  log. The touchpad's I2C drivers stay built in, as proven in the diagnostic kernel. Built-in
  code needs no exports, so Google's ABI list and CRCs should stay intact (`make gki` checks).
  Larger drivers (`amdgpu`, Wi-Fi, audio) stay modules (see [kernel.md](kernel.md)).
- Firmware is never written: SPI-flash and TPM drivers stay blacklisted.

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
3. Write the USB with the owner's approval; read it back and check the ESP files read-only. Not run yet.
4. Boot the laptop. Evidence: a photo of the screen showing the kernel log, saved in `out/`.
   M1 does not claim "boots": that needs a usable Android screen. Not run yet.

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
  not SELinux policy; the decoy is explicitly at `00:03.0`.
- SetupWizard's Next button shows a low-battery dialog in the USB VM (no battery is emulated).
  Setup completion is not part of this test. An extra input probe then lost serial responses
  after a 180-second pause ([log](../../out/m1-validation/b3-input-probe.log)); the passing
  bounded boot checks do not establish longer-running stability.
- The serial shell is UID 2000, not root: modprobe and raw input-event reads are inaccessible.
  The AMD module tree's 1,585 import CRCs were checked statically against actual Google helpers
  ([evidence](../../out/overnight/module-crcs.log)); runtime AMD loading remains unverified.

## Actions
Next, with this spec updated after the physical test:
- [ ] Write the USB — a tool with strict target checks (by-id path, USB transport, not NVMe,
  nothing mounted) run through a sudo task — done when read-back matches the image and the
  drive is unmounted again. Needs the owner's explicit approval for the exact device.
- [ ] Boot-file updates on the mounted stick — `make android-deploy USB=…` using
  [deploy.py](../../tools/deploy.py)'s `android` kind — done when a changed kernel reaches the
  stick without sudo, the previous build stays selectable in the menu, and a no-op writes nothing.
- [ ] First laptop Android boot — done when an inspected photo shows usable setup and the
  keyboard/touchpad work. If it stops, capture the last log screen rather than claiming success.
  Keep the internal NVMe hidden and Secure Boot disabled; use a SuperSpeed USB port/cable.
- [ ] Find out if the touchpad needs `X86_AMD_PLATFORM_DEVICE` — done when the diagnostic USB
  has been booted with and without it (`make deploy` after removing it from
  [msi-diagnostic.config](../../kernel/msi-diagnostic.config)) and the touchpad result is recorded here.

### Ideas (not approved)
- M4: Wi-Fi (`mt7921e`), Bluetooth (`btusb`), audio (HDA/ACP), battery and suspend.
- A boot logger (an `rdinit` hook writing to the ESP) if photos of the screen are not enough.
- A udev rule for passwordless OS-partition writes to this one USB.

## Handoff log
- 2026-11-01 (this commit) — Prepared the owner's overnight AMD candidate: signed modules,
  official firmware, RADV/Zink/ANGLE and ABI-checked minigbm. UEFI log/UI checks pass, data is
  preserved and no-op takes 16 s. No physical writes; AMD display/input await the owner.
- 2026-11-01 (this commit) — UEFI USB checks pass in separate log/UI configurations; screenshots
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
