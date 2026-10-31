# USB diagnostics

**Status:** parked — works in QEMU; not tested on the laptop; not being developed now.
**Last verified:** 2026-10-31 — `make smoke` (UEFI boot in QEMU, instruction-emulation self-test) and `make test`.

## Goal
A small Linux USB (not Android) to check this laptop's hardware with our own kernel build,
with file-level incremental updates instead of reflashing.

## Current state
Verified in QEMU: GRUB, the source-built kernel and BusyBox boot through UEFI; logs saved to the USB;
both supported instruction encodings trap into the emulator; clean poweroff; `make deploy`
writes only changed files and nothing on a no-op.
Not verified: flashing a real USB, booting the laptop.

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
  laptop is reviewed. Needs the user to flash a USB.

## Handoff log
- 2026-10-31 (this commit) — BusyBox and GRUB are official/Debian prebuilts instead of source
  builds; `scripts/busybox.sh` and `scripts/grub.sh` removed. Checked by `make smoke`, `make test`
  and a QEMU boot without a serial port (GRUB does not pause).
- 2026-10-31 `73027fe` — Source-built diagnostic USB and incremental deploy; nine tests.
