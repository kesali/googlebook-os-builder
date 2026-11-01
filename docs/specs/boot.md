# Boot chain

**Status:** working — QEMU boots Google's ramdisks with our modules and settings.
**Last verified:** 2026-11-01 — `make android-uefi-check JOBS=12`: OVMF/GRUB load the disk's
kernel/initrd, first-stage init mounts USB partitions; separate console and setup screenshots
inspected (evidence in [laptop-hardware.md](laptop-hardware.md)).

## Goal
Assemble what a Googlebook's firmware would hand the kernel — command line, initrd, bootconfig —
from Google's boot images plus a short, readable list of our changes.

## Current state
Verified: initrd = Google platform ramdisk + Google module ramdisk extended with our virtio
modules + Google generic ramdisk + bootconfig; slot A boots normally; first-stage mounts succeed.
Also verified through OVMF/GRUB on a disposable USB disk. Not verified: physical firmware or
the transition from simpledrm to Android graphics; the UEFI test checks log and UI separately.

## Decisions
- Command line is Google's, minus Intel-only arguments, minus SPI-flash write enables,
  plus a TPM/SPI-flash driver blacklist — never let Google's tools write firmware.
- Bootconfig is Google's plus [android/bootconfig.txt](../../android/bootconfig.txt): slot A,
  orange/unlocked verified boot, external boot source, StrongBox disabled.
- Only the QEMU modules needed are added: `virtio_dma_buf`, `virtio-gpu`, `virtio_input`,
  `failover`, `net_failover`, `virtio_net` — Google's prebuilt, unsigned copies from its
  virtual-device build of our exact kernel release.
- GRUB detects the MSI's PCI `1002:15e7` and passes `androidboot.dali.graphics=amd`.
  Otherwise it selects softpipe; Android's shared init file imports the matching profile.
  AMD modules load by PCI alias from vendor_dlkm after vendor firmware is available, not
  from the first-stage module ramdisk.

## Files
- [android/cmdline.txt](../../android/cmdline.txt) — one argument per line, with reasons.
- [boot/android-menu.cfg](../../boot/android-menu.cfg) — laptop GRUB menu, also used by the UEFI check; the direct-kernel VM does not use it.
- [tools/android_uefi_test.py](../../tools/android_uefi_test.py) — OVMF/GRUB and USB-partition checks with an NVMe decoy.
- [android/bootconfig.txt](../../android/bootconfig.txt), [tools/bootconfig.py](../../tools/bootconfig.py) — settings and packing.
- [android/module_ramdisk/](../../android/module_ramdisk/) — first-stage modules (`install.list`) and their load lines (`modules.patch`).
- [scripts/android-modules.sh](../../scripts/android-modules.sh) — applies them; checks the kernel release and `modules.patch` dependencies against Google's QEMU driver build.
- [scripts/android-initrd.sh](../../scripts/android-initrd.sh) — initrd assembly.

## Verify
`make android-initrd`, then `make qemu-check JOBS=12`. Kernel and init log: `out/qemu/kernel.log`.

## Pitfalls
- `modules.dep` lines without dependencies must be `name:` with **no trailing space**; Android
  reads `"name: "` as an empty dependency and hangs (`malformed module name`). Regression test in
  [tests/test_overlay.py](../../tests/test_overlay.py).
- Anything appended after Google's lz4-legacy ramdisks must also be lz4-legacy (`lz4 -l`).
- Bootconfig must end the initrd (data, NUL padding to 4 bytes, size, checksum, `#BOOTCONFIG\n`)
  and the command line must contain `bootconfig`.
- The direct-kernel VM uses NVMe 0; USB boot finds its disk through EFI-SYSTEM's PARTUUID.
- Google's built-in command line selects `console=ttynull`; the laptop menu must explicitly
  add `console=drm_log` or the screen log will not register.
- Ramdisk packing normalises timestamps so unchanged inputs give identical bytes.

## Actions
_None agreed._ Physical boot and graphics handoff are tracked in [laptop-hardware.md](laptop-hardware.md).

## Handoff log
- 2026-11-01 (this commit) — Added PCI-selected graphics profiles and GRUB's setpci module.
  The new image still passes both UEFI checks, with softpipe selected and its init import
  confirmed in the kernel log; direct boot also selects the default. AMD handoff awaits the laptop.
- 2026-11-01 (this commit) — Verified OVMF/GRUB loading GKI and first-stage USB mounts; added
  `console=drm_log` to override the built-in null-console selection. No kernel/ramdisk changes.
  The UEFI test keeps log and graphical checks separate; laptop boot remains untested.
- 2026-11-01 `deee56b` — Added `boot/android-menu.cfg`, the laptop's GRUB entry: this command
  line (flattened by deploy.py, which rejects words needing GRUB quoting) plus laptop-only
  arguments. Written into the ESP by `make android-boot`; not booted through firmware yet.
- 2026-10-31 `9dfd0cf` — QEMU modules are Google's prebuilt ones (`GKI_VIRT`), not compiled
  here. Checked by `make qemu-check` (all six load; GPU, input and Ethernet up).
- 2026-10-31 `357470d` — First-stage modules declared in android/module_ramdisk/ (install.list + modules.patch); dependencies checked against the kernel build. Ramdisk byte-identical.
- 2026-10-31 `56719c0` — Added virtio GPU/input/net modules; fixed trailing-space module list hang.
- 2026-10-31 `2f02300` — First headless boot from Google's unmodified partitions.
