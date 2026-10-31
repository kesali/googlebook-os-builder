# Boot chain

**Status:** working — QEMU boots Google's ramdisks with our modules and settings.
**Last verified:** 2026-10-31 — `make qemu-check`: Android reaches `sys.boot_completed=1` and the setup screen.

## Goal
Assemble what a Googlebook's firmware would hand the kernel — command line, initrd, bootconfig —
from Google's boot images plus a short, readable list of our changes.

## Current state
Verified: initrd = Google platform ramdisk + Google module ramdisk extended with our virtio
modules + Google generic ramdisk + bootconfig; slot A boots normally; first-stage mounts succeed.
Not verified: booting through real firmware (QEMU loads kernel and initrd directly).

## Decisions
- Command line is Google's, minus Intel-only arguments, minus SPI-flash write enables,
  plus a TPM/SPI-flash driver blacklist — never let Google's tools write firmware.
- Bootconfig is Google's plus [android/bootconfig.txt](../../android/bootconfig.txt): slot A,
  orange/unlocked verified boot, external boot source, StrongBox disabled.
- Only the QEMU modules needed are added: `virtio_dma_buf`, `virtio-gpu`, `virtio_input`,
  `failover`, `net_failover`, `virtio_net`. vgem is deliberately not loaded.

## Files
- [android/cmdline.txt](../../android/cmdline.txt) — one argument per line, with reasons.
- [android/bootconfig.txt](../../android/bootconfig.txt), [tools/bootconfig.py](../../tools/bootconfig.py) — settings and packing.
- [scripts/android-modules.sh](../../scripts/android-modules.sh), [tools/qemu_modules.py](../../tools/qemu_modules.py) — first-stage modules.
- [scripts/android-initrd.sh](../../scripts/android-initrd.sh) — initrd assembly.

## Verify
`make android-initrd`, then `make qemu-check JOBS=12`. Kernel and init log: `out/qemu/kernel.log`.

## Pitfalls
- `modules.dep` lines without dependencies must be `name:` with **no trailing space**; Android
  reads `"name: "` as an empty dependency and hangs (`malformed module name`). Regression test exists.
- Anything appended after Google's lz4-legacy ramdisks must also be lz4-legacy (`lz4 -l`).
- Bootconfig must end the initrd (data, NUL padding to 4 bytes, size, checksum, `#BOOTCONFIG\n`)
  and the command line must contain `bootconfig`.
- The disk must appear as NVMe 0; Android treats other NVMe disks as removable storage.
- Ramdisk packing normalises timestamps so unchanged inputs give identical bytes.

## Actions
_None agreed._ Change only when a VM or laptop need appears.

## Handoff log
- 2026-10-31 `56719c0` — Added virtio GPU/input/net modules; fixed trailing-space module list hang.
- 2026-10-31 `2f02300` — First headless boot from Google's unmodified partitions.
