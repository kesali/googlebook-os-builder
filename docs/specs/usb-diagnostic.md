# USB diagnostics

**Status:** parked — works in QEMU; not tested on the laptop; not being developed now.
**Last verified:** 2026-10-31 — `make smoke` (UEFI boot in QEMU, instruction-emulation self-test) and `make test`.

## Goal
A small Linux USB (not Android) built entirely from source to check this laptop's hardware,
with file-level incremental updates instead of reflashing.

## Current state
Verified in QEMU: source-built kernel, BusyBox and GRUB boot through UEFI; logs saved to the USB;
both supported instruction encodings trap into the emulator; clean poweroff; `make deploy`
writes only changed files and nothing on a no-op.
Not verified: flashing a real USB, booting the laptop.

## Decisions
- Separate diagnostic kernel ([kernel/msi-diagnostic.config](../../kernel/msi-diagnostic.config)): GCC,
  no modules; **not** GKI-compatible, so it cannot run Android.
- Internal NVMe/SATA/MMC, SPI flash, TPM and EFI capsule writing are disabled in this kernel.
- Updates go to an already-mounted USB with the Dali marker; content-addressed kernel/initramfs
  files; the boot menu switches last; the previous menu is kept.

## Files
- [boot/init](../../boot/init), [boot/menu.cfg](../../boot/menu.cfg), [boot/loader.cfg](../../boot/loader.cfg) — runtime and boot menus.
- [scripts/kernel.sh](../../scripts/kernel.sh), [scripts/busybox.sh](../../scripts/busybox.sh), [scripts/grub.sh](../../scripts/grub.sh), [scripts/initramfs.sh](../../scripts/initramfs.sh), [scripts/image.sh](../../scripts/image.sh).
- [tools/deploy.py](../../tools/deploy.py), [tests/test_deploy.py](../../tests/test_deploy.py), [tools/boot_test.py](../../tools/boot_test.py).

## Verify
`make test`, `make smoke`. Deploy: `make deploy USB=/run/media/$USER/DALI-BOOT`.

## Pitfalls
- GRUB 2.12's tarball lacks the empty `grub-core/extra_deps.lst`; the build creates it. Its awk script needs gawk.
- A rootless cpio has no `/dev/console`; init redirects output after mounting devtmpfs.
- Legacy SSE-encoded GFNI still raises SIGILL (see [kernel.md](kernel.md)).

## Actions
- [ ] Boot the diagnostic USB on the laptop — done when `/boot/logs/hardware.txt` from the real
  laptop is reviewed. Needs the user to flash a USB.

## Handoff log
- 2026-10-31 `73027fe` — Source-built diagnostic USB and incremental deploy; nine tests.
