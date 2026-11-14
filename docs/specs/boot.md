# Boot chain

**Status:** partial — the corrected policy boots in enforcing QEMU and writes ext4 diagnostic
logs; physical boot and retrieval with this policy remain unverified.
**Last verified:** 2026-11-14 — focused tests and disposable-image QEMU boot; ext4 kernel
and Android logs were nonempty. QEMU input and physical capture were not checked.

## Goal
Assemble Google's boot images, initrd and boot configuration with the smallest set of
source-based changes needed for QEMU and the laptops.

## Current state
The initrd combines Google's ramdisks with the declared first-stage modules and
bootconfig. GRUB identifies device quirks by the known GPU IDs; init is configured to
select the AMD, Intel ANV/HasVK, or softpipe profile after DRM binding. Selection completes
before the profile runs and Zygote starts; this ordering is verified for enforcing QEMU
softpipe but not on physical GPUs. The bounded screenshot reaches Android's welcome screen.
Diagnostic logging is opt-in and the new image builder formats the dedicated `GBOS-LOGS`
partition as ext4; a disposable QEMU image mounted ext4 and wrote logs. Normal boots
do not mount it or rotate saved logs. Berberis is the default
native bridge, with a persistent GRUB choice for Houdini. The owner confirms firmware-free
boots on both laptops. MSI diagnostic logs were reviewed from the previous image.

## Decisions
- Keep Google's command line except for disabling firmware-write paths and hardware
  arguments that do not apply. EFI pstore is disabled; this does not prevent all firmware
  writes.
- Keep diagnostics opt-in, bounded, and in a dedicated enforcing SELinux domain. Do not
  fall back to metadata or format the log partition when it is unavailable.
- Preserve the saved GRUB native-bridge choice across boot updates. Berberis is the
  default; diagnostics do not alter the saved choice.
- Keep normal screen logging disabled; use a separate early-console entry for diagnosis.
- Use Google's prebuilt QEMU modules for the pinned kernel release and verify their
  dependency metadata.

## Files
- [android/cmdline.txt](../../android/cmdline.txt) and
  [android/bootconfig.txt](../../android/bootconfig.txt) — kernel arguments and bootconfig.
- [scripts/android-initrd.sh](../../scripts/android-initrd.sh) and
  [android/module_ramdisk/](../../android/module_ramdisk/) — initrd assembly and modules.
- [boot/android-menu.cfg](../../boot/android-menu.cfg) — laptop GRUB menu.
- [tools/deploy.py](../../tools/deploy.py) — safe boot-file updates and saved choice.
- [android/system_ext/bootlog.rc](../../android/system_ext/bootlog.rc),
  [bootlog-prepare.sh](../../android/system_ext/bootlog-prepare.sh) — diagnostic logging.

## Verify
Run `make android-initrd` and `make qemu-check`. For boot changes, inspect the screen,
logs, SELinux denials and diagnostic files. Focused logging tests:
`scripts/builder.sh python3 -m unittest discover -s tests -p test_bootlog.py -v`.

## Pitfalls
- Ramdisks appended after Google's legacy LZ4 ramdisks must also use legacy LZ4.
- Bootconfig must be the final initrd payload and the command line must include `bootconfig`.
- `modules.dep` entries without dependencies must be `name:` with no trailing space.
- Never replay a journal on the physical USB. Recover only from an owner-approved copy.
- FAT32 log partitions are unsupported; retrieval never repairs a filesystem.
- Ext4 journals filesystem metadata; it cannot guarantee recent log data survives power loss.
- QEMU logged `installd` quota-query denials on the log filesystem; their impact is unverified.

## Actions
- [ ] Verify ext4 diagnostic logging on a fresh installation — done when a diagnostic boot
  writes logs that `make laptop-logs` retrieves successfully.
