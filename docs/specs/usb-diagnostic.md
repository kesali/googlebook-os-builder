# USB diagnostics

**Status:** parked — renamed diagnostic image verified in QEMU; previous laptop boot confirmed.
**Last verified:** 2026-11-04 — `make image smoke JOBS=12` passes: new label/marker/path and
readiness signal reach the source-built kernel through UEFI/GRUB, both emulated instructions
pass, logs/report persist and guest powers off. No physical write or retest.
[Evidence](../../out/gbos-builder-validation/diagnostic-smoke.log).

Earlier, 2026-10-31 — owner's laptop test; saved
[hardware report](../../out/laptop-boot-2026-10-31/hardware.txt) and
[kernel log](../../out/laptop-boot-2026-10-31/kernel.log) reviewed.
Image rebuilt from `4360357`; `make test smoke JOBS=12`, physical USB read-back, GPT and FAT checks passed.
[Build, image checksum, payload checks, boot logs and console screenshots](../../out/usb-validation-4360357/).

## Goal
A small Linux USB (not Android) to check this laptop's hardware with our own kernel build,
with file-level incremental updates instead of reflashing.

## Current state
Verified: clean-break gbos-builder identity uses `GBOS-BOOT`, `gbos-builder/`,
new format marker and kernel arguments. Old diagnostic media are not compatible update
targets. New output is `out/gbos-builder-usb.img`; existing images are preserved.
Not verified: renamed diagnostic image on physical hardware or its interactive keyboard path.

Verified in QEMU: GRUB, the source-built kernel and BusyBox boot through UEFI; logs saved to the USB;
both supported instruction encodings trap into the emulator; clean poweroff; `make deploy`
writes only changed files and nothing on a no-op.
The default interactive menu also boots without a serial port: the visible console, keyboard
command execution, saved report and clean shutdown were verified on a disposable image copy.
Physical USB: written with the owner's explicit approval; full-image read-back matched.
The backup GPT was moved to the drive's end; the boot filesystem still matched the image,
and read-only FAT checks passed. The USB was left unmounted.
First laptop test: the owner reported successful boot and shutdown. The saved logs show the
MSI Modern 15 B7M running the expected kernel, `ISA_SMOKE_OK` for both supported encodings,
simpledrm console initialization, keyboard registration and the ELAN0307 I2C HID/multitouch
device. The partition report contains only the USB disk and its partition, not internal NVMe.
Not verified: physical touchpad motion/gestures, Wi-Fi, Bluetooth, audio or Android on the laptop.
The log ends at the self-test; shutdown is the owner's observation, not captured in the log.

## Decisions
- BusyBox is busybox.net's official static binary and GRUB is Debian's package, both unchanged:
  we change neither, so neither is compiled here. Only the kernel (instruction emulator) is.
- Separate diagnostic kernel ([kernel/msi-diagnostic.config](../../kernel/msi-diagnostic.config)): GCC,
  no modules; **not** GKI-compatible, so it cannot run Android.
- Internal NVMe/SATA/MMC, SPI flash, TPM and EFI capsule writing are disabled in this kernel.
- Updates go to an already-mounted USB with the gbos-builder marker; content-addressed kernel/initramfs
  files; the boot menu switches last; the previous menu is kept.

## Files
- [boot/init](../../boot/init), [boot/menu.cfg](../../boot/menu.cfg), [boot/loader.cfg](../../boot/loader.cfg) — runtime and boot menus.
- [scripts/kernel.sh](../../scripts/kernel.sh), [scripts/initramfs.sh](../../scripts/initramfs.sh), [scripts/image.sh](../../scripts/image.sh).
- [tools/deploy.py](../../tools/deploy.py), [tests/test_deploy.py](../../tests/test_deploy.py), [tools/boot_test.py](../../tools/boot_test.py).

## Verify
`make test`, `make smoke`. Deploy: `make deploy USB=/run/media/$USER/GBOS-BOOT`.

## Pitfalls
- Debian's GRUB names the boot device in `$fw_path`, not upstream's `$cmdpath` (Debian patch
  `add-fw_path-variable-to-detect-config-file-on-efi`). With `$cmdpath` it stops at `grub>`.
- A rootless cpio has no `/dev/console`; init redirects output after mounting devtmpfs.
- Legacy SSE-encoded GFNI still raises SIGILL (see [kernel.md](kernel.md)).
- The first laptop log has ACPI table errors, missing `regulatory.db` and an HDMI HDA codec
  probe failure. They did not prevent this diagnostic boot; Wi-Fi/audio and power-management
  behavior are not validated by this test.

## Actions
_None agreed._ The BUP Slim moves to the Android layout ([laptop-hardware.md](laptop-hardware.md));
flash this image again only when a hardware check is needed.

## Handoff log
- 2026-11-04 (this commit) — Rename diagnostic marker/path/label, kernel build identity and
  readiness signal. 246 tests and rebuilt UEFI smoke pass with saved logs and clean poweroff;
  no physical writes, retest or history changes.
- 2026-11-01 (this commit) — deploy.py gained a second bundle kind (`android`, for the laptop's
  disk); the diagnostic marker bytes and flow are unchanged. `make test`, `make usb` and `make smoke`
  pass; `make deploy` to a mounted stick was not re-run (its tests are in `test_deploy.py`).
- 2026-10-31 `9c78a5d` — Parked: the stick is being repurposed for Android; the diagnostic
  image stays buildable with `make usb`. No code changes.
- 2026-10-31 `af0f7b6` — Owner confirmed first laptop boot/shutdown; reviewed and preserved
  both USB logs. Instruction tests pass, ELAN multitouch registers and internal NVMe is absent
  from the block-device report. Touchpad motion and Android remain untested.
- 2026-10-31 `8626359` — Flashed the explicitly approved USB; read-back, GPT and FAT checks
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
