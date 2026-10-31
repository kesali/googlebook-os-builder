# Laptop hardware

**Status:** planned — Android has not been booted on the MSI laptop yet.
**Last verified:** — (only the separate diagnostic USB has a source-built kernel for this laptop)

## Goal
Run the same Googlebook OS on the **MSI Modern 15 B7M** (Ryzen 5 7530U, Radeon Vega graphics,
MT7922 Wi-Fi/Bluetooth, ELAN touchpad, HDA/ACP audio), adding drivers one at a time and
updating the USB incrementally instead of reflashing.

## Current state
Not started for Android. The QEMU work shares the kernel, boot chain and OS image with this.

| Part | Needed for Android |
|---|---|
| Display / GPU | `amdgpu` module, Mesa radeonsi/RADV, minigbm/composer for AMD |
| Keyboard, touchpad | i8042/AT keyboard, AMD GPIO + I2C HID (ELAN0307) |
| Wi-Fi / Bluetooth | `mt7921e`, `btusb`/`btmtk` + firmware |
| Audio | HDA + AMD ACP |
| Storage | Boot from USB first; internal NVMe stays untouched |

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

## Actions
- [ ] Plan the first laptop boot — done when the user agrees on: USB layout, how partitions are
  updated incrementally on the USB, and the first driver set (display + keyboard).

## Handoff log
- 2026-10-31 — Spec created; no laptop Android work yet.
