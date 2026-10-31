# Laptop hardware

**Status:** planned — Android has not been booted on the MSI laptop yet.
**Last verified:** 2026-10-31 — diagnostic USB only: owner confirmed boot/shutdown;
[hardware report](../../out/laptop-boot-2026-10-31/hardware.txt) and
[kernel log](../../out/laptop-boot-2026-10-31/kernel.log) reviewed.

## Goal
Run the same Googlebook OS on the **MSI Modern 15 B7M** (Ryzen 5 7530U, Radeon Vega graphics,
MT7922 Wi-Fi/Bluetooth, ELAN touchpad, HDA/ACP audio), adding drivers one at a time and
updating the USB incrementally instead of reflashing.

## Current state
Not started for Android. The QEMU work shares the kernel, boot chain and OS image with this.
The first diagnostic boot passed both instruction-emulation tests and registered the internal
keyboard and ELAN0307 touchpad with `hid-multitouch`. Pointer motion/gestures were not tested.
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
- QEMU first; the laptop comes after the VM is usable. No installer and no dual boot for now.
- New drivers are GKI **modules** (see [kernel.md](kernel.md)), so Google's kernel and modules stay intact.
- Firmware is never written: SPI-flash and TPM drivers stay blacklisted.

## Files
- [kernel/gki.config](../../kernel/gki.config) — where driver modules will be added.
- [android/cmdline.txt](../../android/cmdline.txt) — Intel arguments already removed.
- Reference ports (not in Git): `reference/project-churro-msi-modern-15-B7M`, `reference/gbos-x86-msi-modern-15-B7M`.

## Verify
To be defined with the first action.

## Pitfalls
- Googlebook userspace uses instructions this CPU lacks; the kernel's emulator patch is required (see [kernel.md](kernel.md)).
- The touchpad needs `X86_AMD_PLATFORM_DEVICE` (built-in only: it sets the AMD I2C clock),
  `PINCTRL_AMD`, `I2C_DESIGNWARE_PLATFORM` and `I2C_HID_ACPI`; Google's GKI config has none of them.
  The diagnostic USB enables all of them and registers the touchpad; motion/gestures and the
  comparison without `X86_AMD_PLATFORM_DEVICE` are still untested.
  The reference port never got this touchpad working.

## Actions
- [ ] Plan the first laptop boot — done when the user agrees on: USB layout, how partitions are
  updated incrementally on the USB, and the first driver set (display + keyboard).
- [ ] Find out if the touchpad needs `X86_AMD_PLATFORM_DEVICE` — done when the diagnostic USB
  has been booted with and without it (`make deploy` after removing it from
  [msi-diagnostic.config](../../kernel/msi-diagnostic.config)) and the touchpad result is recorded here.

## Handoff log
- 2026-10-31 (this commit) — First diagnostic boot/shutdown confirmed by the owner; logs show
  ELAN0307 I2C HID/multitouch registration and passing instruction tests. No Android boot or
  touchpad motion test yet; no driver/config changes made.
- 2026-10-31 `81c4536` — Device IDs and drivers recorded from the laptop's desktop Linux;
  touchpad drivers added to the diagnostic kernel. Not yet booted on the laptop.
- 2026-10-31 — Spec created; no laptop Android work yet.
