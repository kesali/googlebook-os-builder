# Laptop hardware

**Status:** planned — first boot plan (M1) agreed; Android has not been booted on the MSI laptop yet.
**Last verified:** 2026-10-31 — diagnostic USB only: owner confirmed boot/shutdown;
[hardware report](../../out/laptop-boot-2026-10-31/hardware.txt) and
[kernel log](../../out/laptop-boot-2026-10-31/kernel.log) reviewed. The BUP Slim was measured
read-only: [drive notes](../../out/laptop-boot-2026-10-31/usb-drive.txt).

## Goal
Run the same Googlebook OS on the **MSI Modern 15 B7M** (Ryzen 5 7530U, Radeon Vega graphics,
MT7922 Wi-Fi/Bluetooth, ELAN touchpad, HDA/ACP audio), adding drivers one at a time and
updating the USB incrementally instead of reflashing.

## Current state
Not started for Android. The QEMU work shares the kernel, boot chain and OS image with this.
The first diagnostic boot passed both instruction-emulation tests and registered the internal
keyboard and ELAN0307 touchpad with `hid-multitouch`. Pointer motion/gestures were not tested.
The USB for Android is the BUP Slim (232.9 GiB). It linked at USB 2.0 (480 Mb/s, 39 MB/s
sequential, 0.34 ms random reads); Linux calls it rotational, but the media type is unknown.
In Google's disk (`out/android/disk.img`) EFI-SYSTEM (64 MiB) and `KERN-A` (512 MiB) are all zeros.
Not verified: any Android boot on the laptop, and whether Google's graphics allocator accepts simpledrm.
The devices below were read from this laptop running a desktop Linux (`lspci -nnk`, `lsusb`,
`/proc/bus/input/devices`).

| Part | Device [ID] | Linux driver | Needed for Android |
|---|---|---|---|
| Display / GPU | Radeon "Barcelo" [1002:15e7] | `amdgpu` | `amdgpu` module, Mesa radeonsi/RADV, minigbm/composer for AMD |
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
  laptop. No Android UI yet: Google's graphics allocator probably rejects simpledrm, so the UI
  needs `amdgpu` and Mesa (M2/M3, planned later).
- USB layout: Google's whole GPT, as in `out/android/disk.img`. Android finds its disk by the
  PARTUUID of EFI-SYSTEM (`androidboot.boot_part_uuid`) and its partitions by name. EFI-SYSTEM
  grows from 64 to 576 MiB by absorbing the blank `KERN-A` beside it and keeps its PARTUUID.
  GRUB, kernel, initrd and menu live there and update like the diagnostic USB
  ([deploy.py](../../tools/deploy.py): new files first, the menu last, previous build kept).
  This replaces the diagnostic image on the stick; flash it again only for a hardware check.
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
- [scripts/android-disk.sh](../../scripts/android-disk.sh) — Google's disk layout, which the USB copies.
- [tools/deploy.py](../../tools/deploy.py), [tools/android_sync.py](../../tools/android_sync.py) — boot-file and OS-partition updaters to adapt.
- [android/cmdline.txt](../../android/cmdline.txt) — Intel arguments already removed.
- Reference ports (not in Git): `reference/project-churro-msi-modern-15-B7M`, `reference/gbos-x86-msi-modern-15-B7M`.

## Verify
Planned for M1, in this order (none of it has been run yet):
1. `make test`, `make gki JOBS=12` (config, ABI and certificate checks), then `make qemu-check JOBS=12`.
2. Boot the USB image in QEMU through UEFI and GRUB with the disk attached as USB storage:
   first-stage init finds its partitions and Android starts as in the direct-kernel boot.
3. Write the USB with the owner's approval; read it back and check the ESP files read-only.
4. Boot the laptop. Evidence: a photo of the screen showing the kernel log, saved in `out/`.
   M1 does not claim "boots": that needs a usable Android screen.

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

## Actions
M1, in order; each step is its own commit with this spec updated.
- [ ] Kernel built-ins — add to [gki.config](../../kernel/gki.config), each with its reason:
  `X86_AMD_PLATFORM_DEVICE`, `PINCTRL_AMD`, `I2C_DESIGNWARE_CORE`, `I2C_DESIGNWARE_PLATFORM`,
  `I2C_HID_ACPI`, `SYSFB_SIMPLEFB`, `DRM_SIMPLEDRM`, `DRM_CLIENT_LOG` — done when `make gki`
  passes its config and ABI checks and `make qemu-check` still reaches the setup screen.
- [ ] Android USB image — turn the Android disk into the USB layout (576 MiB EFI-SYSTEM with GRUB,
  kernel, initrd, menu and a laptop command line) as a regular file — done when QEMU boots it
  through UEFI with the disk attached as USB storage and Android starts as before.
- [ ] Write the USB — a tool with strict target checks (by-id path, USB transport, not NVMe,
  nothing mounted) run through a sudo task — done when read-back matches the image and the
  drive is unmounted again. Needs the owner's explicit approval for the exact device.
- [ ] First laptop boot — done when a photo of the laptop screen shows the kernel log with the
  keyboard and ELAN touchpad registered and Android's first-stage init mounting the USB's
  partitions (or where it stops); record what was not seen.
- [ ] Find out if the touchpad needs `X86_AMD_PLATFORM_DEVICE` — done when the diagnostic USB
  has been booted with and without it (`make deploy` after removing it from
  [msi-diagnostic.config](../../kernel/msi-diagnostic.config)) and the touchpad result is recorded here.

### Ideas (not approved)
- M2: the `amdgpu` module with firmware from an official, pinned linux-firmware tag. Needs the
  kernel's exported-symbol list extended with what amdgpu uses, and
  [kabi_check.py](../../tools/kabi_check.py) relaxed from "identical exports" to "Google's exports
  kept, same CRCs".
- M3: Android's UI on the AMD GPU: an allocator that accepts it, Mesa RADV and ANGLE. Project
  Churro's AMD path is proven on this laptop (see `reference/`), but it is large.
- M4: Wi-Fi (`mt7921e`), Bluetooth (`btusb`), audio (HDA/ACP), battery and suspend.
- A boot logger (an `rdinit` hook writing to the ESP) if photos of the screen are not enough.
- A udev rule for passwordless OS-partition writes to this one USB.

## Handoff log
- 2026-10-31 (this commit) — Owner agreed the first laptop boot plan: Google's GPT with a 576 MiB
  EFI-SYSTEM, boot files via the mounted ESP, OS partitions via a sudo task, M1 first.
  BUP Slim measured at USB 2.0. Plan and QEMU spec updated; no code changes.
- 2026-10-31 `af0f7b6` — First diagnostic boot/shutdown confirmed by the owner; logs show
  ELAN0307 I2C HID/multitouch registration and passing instruction tests. No Android boot or
  touchpad motion test yet; no driver/config changes made.
- 2026-10-31 `81c4536` — Device IDs and drivers recorded from the laptop's desktop Linux;
  touchpad drivers added to the diagnostic kernel. Not yet booted on the laptop.
- 2026-10-31 — Spec created; no laptop Android work yet.
