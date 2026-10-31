# USB diagnostics

**Status:** parked — works in QEMU; not tested on the laptop; not being developed now.
**Last verified:** 2026-10-31 — rebuilt from `4360357`, then `make test smoke JOBS=12`;
physical USB write/read-back, GPT and FAT checks.
[Build, image checksum, payload checks, boot logs and console screenshots](../../out/usb-validation-4360357/).

## Goal
A small Linux USB (not Android) to check this laptop's hardware with our own kernel build,
with file-level incremental updates instead of reflashing.

## Current state
Verified in QEMU: GRUB, the source-built kernel and BusyBox boot through UEFI; logs saved to the USB;
both supported instruction encodings trap into the emulator; clean poweroff; `make deploy`
writes only changed files and nothing on a no-op.
The default interactive menu also boots without a serial port: the visible console, keyboard
command execution, saved report and clean shutdown were verified on a disposable image copy.
Physical USB: written with the owner's explicit approval; full-image read-back matched.
The backup GPT was moved to the drive's end; the boot filesystem still matched the image,
and read-only FAT checks passed. The USB was left unmounted.
Not verified: booting the laptop.

## Decisions
- BusyBox is busybox.net's official static binary and GRUB is Debian's package, both unchanged:
  we change neither, so neither is compiled here. Only the kernel (instruction emulator) is.
- Separate diagnostic kernel ([kernel/msi-diagnostic.config](../../kernel/msi-diagnostic.config)): GCC,
  no modules; **not** GKI-compatible, so it cannot run Android.
- Internal NVMe/SATA/MMC, SPI flash, TPM and EFI capsule writing are disabled in this kernel.
- Updates go to an already-mounted USB with the Dali marker; content-addressed kernel/initramfs
  files; the boot menu switches last; the previous menu is kept.

## Files
- [boot/init](../../boot/init), [boot/menu.cfg](../../boot/menu.cfg), [boot/loader.cfg](../../boot/loader.cfg) — runtime and boot menus.
- [scripts/kernel.sh](../../scripts/kernel.sh), [scripts/initramfs.sh](../../scripts/initramfs.sh), [scripts/image.sh](../../scripts/image.sh).
- [tools/deploy.py](../../tools/deploy.py), [tests/test_deploy.py](../../tests/test_deploy.py), [tools/boot_test.py](../../tools/boot_test.py).

## Verify
`make test`, `make smoke`. Deploy: `make deploy USB=/run/media/$USER/DALI-BOOT`.

## Pitfalls
- Debian's GRUB names the boot device in `$fw_path`, not upstream's `$cmdpath` (Debian patch
  `add-fw_path-variable-to-detect-config-file-on-efi`). With `$cmdpath` it stops at `grub>`.
- A rootless cpio has no `/dev/console`; init redirects output after mounting devtmpfs.
- Legacy SSE-encoded GFNI still raises SIGILL (see [kernel.md](kernel.md)).

## Actions
- [ ] Boot the diagnostic USB on the laptop — done when `/boot/logs/hardware.txt` from the real
  laptop is reviewed. The USB is flashed; the user needs to boot it.

## Handoff log
- 2026-10-31 (this commit) — Flashed the explicitly approved USB; read-back, GPT and FAT checks
  passed. [Flash log](../../out/usb-validation-4360357/flash.log) retained; one-time flashing
  script/task removed. Laptop boot remains untested.
- 2026-10-31 `0e6bd03` — Rebuilt the current prebuilt-based image; verified payload hashes,
  22 tests, UEFI smoke and no-serial console/input. A no-op build took 4 s and preserved all
  published contents and timestamps. Evidence above; physical laptop boot remains untested.
- 2026-10-31 `b3f7488` — `hardware.txt` lists PCI/USB devices with their drivers, input
  and I2C devices; `make smoke` checks the USB controller's driver appears.
- 2026-10-31 `bb5a38f` — BusyBox and GRUB are official/Debian prebuilts instead of source
  builds; `scripts/busybox.sh` and `scripts/grub.sh` removed. Checked by `make smoke`, `make test`
  and a QEMU boot without a serial port (GRUB does not pause).
- 2026-10-31 `73027fe` — Source-built diagnostic USB and incremental deploy; nine tests.
