# Boot chain

**Status:** partial — the laptop completed setup; its boot logs and snapshot are retrieved after each test.
**Last verified:** 2026-11-02 — the owner retrieved the laptop's `/dali-bootlog/current/` from
its `95b3bf6` boot ([snapshot](../../out/laptop-boot-2026-11-02-hdmi/current/hardware.txt)): it
records the eDP `backlight` device and labels, ALC256 on card1 and the loaded HDA modules.
Before that, a readiness-gated snapshot was recovered from a disposable enforcing
QEMU boot ([snapshot](../../out/hardware-fixes-validation/final-production-hardware.txt)).
It exits successfully and does not run before boot-log preparation succeeds.
Earlier, `make test` passed 87 tests; `make android-image JOBS=12` rebuilt
the changed partitions with 0 missing/changed kABI exports, and the repeat wrote nothing. The
graphical QEMU smoke test on a reflinked disk copy completed with SELinux enforcing; the setup
screen was inspected and the snapshot file was recovered
([screen](../../out/hardware-snapshot-validation/screen.png),
[snapshot](../../out/hardware-snapshot-validation/hardware.txt)). The owner previously booted the
normal USB entry, joined Wi-Fi and completed setup; keyboard and touchpad work. Offline
disposable UEFI boots show the unguarded control registers EFI pstore, while both guarded entries
disable it and have no active backend. The QEMU monitor read the matching kernel's state with
SELinux enforcing; the NVMe decoy remained unchanged
([control](../../out/efi-pstore-validation/r2/android-uefi-console-o7dyqias/pstore-state.txt),
[normal](../../out/efi-pstore-validation/r2/android-uefi-console-fcizhhsi/pstore-state.txt),
[test](../../out/efi-pstore-validation/r2/android-uefi-console-jram4zg1/pstore-state.txt)).
The owner installed the safeguarded handoff kernel on the USB and
[read-back matched](../../out/framebuffer-handoff-evidence/usb-update-readback.txt).
The saved previous menu may still enable EFI pstore.
2026-11-01 — owner video/photo and read-only EFI crash records show an RCU
stall and hard lockup during duplicate `i2c_hid_acpi` module cleanup. The stall began before
the duplicate-driver error; its cause is unknown. The panic wrote 21 EFI crash records.
Earlier, 35 focused deployment/boot tests and `grub-script-check` passed.
Two offline disposable UEFI boots confirm the normal and test arguments, simpledrm present
and absent respectively, and an unchanged, hidden NVMe decoy
([normal](../../out/grub-menu-validation/android-uefi-console-p9j_qvvh/storage.txt),
[test](../../out/grub-menu-validation/android-uefi-console-feac_k03/storage.txt)).
The owner updated the USB menu; read-back verified it and its backup, and `grub-script-check`
passed on the new menu. Kernel, initramfs and UEFI loader were unchanged. These checks do not
prove a usable screen.
Earlier, 19 focused boot-log/overlay tests, an image rebuild and three
disposable UEFI boots: enforcing collectors, Linux-readable streams and two-boot retention pass
([results](../../out/bootlog-validation/persistence-checked.log),
[setup screenshot](../../out/bootlog-validation/rotation-checked/boot-3/screen.png) inspected).
Earlier separate console/UI UEFI checks also pass; physical AMD acceleration remains unverified.

## Goal
Assemble what a Googlebook's firmware would hand the kernel — command line, initrd, bootconfig —
from Google's boot images plus a short, readable list of our changes.

## Current state
Verified: initrd = Google platform ramdisk + Google module ramdisk extended with our virtio
modules + Google generic ramdisk + bootconfig; slot A boots normally; first-stage mounts succeed.
Also verified through OVMF/GRUB on disposable USB disks for both menu entries.
The normal physical boot completed setup on the AMD desktop with working Wi-Fi, keyboard and
touchpad. Actual GPU acceleration remains unverified. The framebuffer-free test reached
Android early-init and panicked; its metadata logs are from the earlier boot.
Native logcat collectors now save kernel/init and Android logs under `/metadata/dali-bootlog/`.
Three QEMU boots verified current/previous retention, archive limits and no logger SELinux
denials. The largest observed stream was 2,055,373 bytes; policy compilation took 0.54–0.61 s.
The diagnostic candidate was transferred and booted on the laptop; its saved logs were
recovered after journal replay on an owner-approved RAM copy of metadata.
The recovered logs show no backlight path and no loaded HDA/ALSA card. The one-shot, read-only
snapshot now runs in QEMU under its dedicated enforcing domain, with no matching SELinux denials;
QEMU does not expose the laptop's backlight or ALC256 hardware. The owner booted the snapshot
image but reported sound/brightness still broken; its latest USB logs were inaccessible during
the autonomous investigation. The snapshot now also reports backlight permission/SELinux labels,
requires both boot completion and log-preparation readiness, and rejects directory/symlink outputs.

## Decisions
- Command line is Google's, minus Intel-only arguments, minus SPI-flash write enables,
  plus a TPM/SPI-flash driver blacklist — never let Google's tools write firmware.
- Disable EFI pstore with `efi_pstore.pstore_disable=1` so that backend does not write UEFI
  crash records. This does not prevent other firmware writes. The existing records are untouched;
  saved previous menus keep their old arguments and are warned about in GRUB. QEMU validation
  and USB menu read-back passed; the owner later booted the normal entry and completed setup.
  The EFI pstore backend itself has not been queried on the laptop.
- Bootconfig is Google's plus [android/bootconfig.txt](../../android/bootconfig.txt): slot A,
  orange/unlocked verified boot, external boot source, StrongBox disabled.
- Only the QEMU modules needed are added: `virtio_dma_buf`, `virtio-gpu`, `virtio_input`,
  `failover`, `net_failover`, `virtio_net` — Google's prebuilt, unsigned copies from its
  virtual-device build of our exact kernel release.
- GRUB detects the MSI's PCI `1002:15e7` and passes `androidboot.dali.graphics=amd`.
  Otherwise it selects softpipe; Android's shared init file imports the matching profile.
  AMD modules load by PCI alias from vendor_dlkm after vendor firmware is available, not
  from the first-stage module ramdisk.
- A separate, non-default GRUB entry tests `initcall_blacklist=sysfb_init` without removing the
  NVMe blacklist. It is an experiment, not a proven display fix.
- Persistent diagnostics use Google's logcat and `ro.logd.kernel=true`, not a custom logger.
  The owner approved a dedicated enforcing domain, a small rotation/readiness helper and
  Linux retrieval from unencrypted metadata. Only current/previous boot are retained.
  Each stream rotates at 256 KiB with seven archives, leaving headroom below the agreed
  16 MiB per stream per boot and space for other files on the 64 MiB metadata partition.
  Collection begins at `post-fs`, not first-stage init; an earlier hang still needs a photo.
- A one-shot diagnostic gated by both `sys.boot_completed=1` and `sys.dali.bootlog.ready=1`
  may read backlight, ALSA and loaded-module metadata
  into the current boot log directory. It must not read sound device nodes or write sysfs, and it
  uses a separate enforcing SELinux domain.

## Files
- [android/cmdline.txt](../../android/cmdline.txt) — one argument per line, with reasons.
- [boot/android-menu.cfg](../../boot/android-menu.cfg) — laptop GRUB menu, also used by the UEFI check; the direct-kernel VM does not use it.
- [tools/android_uefi_test.py](../../tools/android_uefi_test.py) — OVMF/GRUB and USB-partition checks with an NVMe decoy.
- [android/bootconfig.txt](../../android/bootconfig.txt), [tools/bootconfig.py](../../tools/bootconfig.py) — settings and packing.
- [android/module_ramdisk/](../../android/module_ramdisk/) — first-stage modules (`install.list`) and their load lines (`modules.patch`).
- [scripts/android-modules.sh](../../scripts/android-modules.sh) — applies them; checks the kernel release and `modules.patch` dependencies against Google's QEMU driver build.
- [scripts/android-initrd.sh](../../scripts/android-initrd.sh) — initrd assembly.
- [android/system_ext/bootlog.rc](../../android/system_ext/bootlog.rc),
  [bootlog-prepare.sh](../../android/system_ext/bootlog-prepare.sh),
  [hardware-snapshot.sh](../../android/system_ext/hardware-snapshot.sh) — native collectors,
  two-boot rotation and the one-shot read-only hardware snapshot.
- [android/system/bootlog-policy.patch](../../android/system/bootlog-policy.patch),
  [bootlog-file-contexts.patch](../../android/system/bootlog-file-contexts.patch),
  [bootlog-property-contexts.patch](../../android/system/bootlog-property-contexts.patch) —
  the dedicated domain, directory and readiness property. Google's precompiled vendor policy
  is removed through [remove.list](../../android/vendor/remove.list), so init compiles the text policy.
- [tests/test_bootlog.py](../../tests/test_bootlog.py) — retention, interrupted rotation,
  snapshot safety, failure reporting and readiness gates.

## Verify
`make android-initrd`, then `make qemu-check JOBS=12`. Kernel and init log: `out/qemu/kernel.log`.
To recheck EFI pstore without hardware writes, run the
[validation driver](../../out/efi-pstore-validation/check.py):
`scripts/builder.sh python3 out/efi-pstore-validation/check.py out/efi-pstore-validation/NEW-RUN`.
Use a new evidence directory; the unguarded control runs only in an offline disposable guest.
Focused tests: `scripts/builder.sh python3 -m unittest discover -s tests -p test_bootlog.py -v`
and the same command with `test_overlay.py`. Rebuild with `make android-image JOBS=12`.
The ignored [validation driver](../../out/bootlog-validation/check.py) boots three times,
checks enforcing native collectors/NVMe preservation, and extracts only our logs with debugfs:
`scripts/builder.sh python3 out/bootlog-validation/check.py out/bootlog-validation/NEW-RUN`.
Use a new evidence directory. Mocked tests cover same-boot helper restarts; runtime collector
restart behavior itself was not exercised. Inspect the screenshot, actual files and denials.

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
- Disposable UEFI checks add a serial console that disables EFI earlycon. The laptop test lacks
  it and showed slow firmware logging, so the QEMU pass does not rule out a console-related stall.
- A boot-file update saves the current menu as `grub.previous.cfg`, replacing any older backup.
  Inspect that backup before asking the owner to update the USB.
- Ramdisk packing normalises timestamps so unchanged inputs give identical bytes.
- Logcat long format keeps one header per record, avoiding multiline expansion. On collector
  restart it may replay buffered records; it appends and rotates rather than clearing the boot.
  Directory rotation happens only when the kernel boot ID changes.
- The metadata filesystem is journalled: after a power cut, `ro,noload` or debugfs may show
  stale inodes until the journal is replayed. Never replay it on the USB; the owner may approve
  recovery on a temporary RAM copy. An abrupt power cut can still lose the latest log tail.
  Do not unplug a running laptop. Kernel messages before logd starts can also leave its ring.
  Google's native file output also uses a stdio buffer: a short final message may remain in
  memory until more logs arrive. Persistence checks must distinguish this from a missing stream;
  these collectors do not guarantee every final byte survives a hang or power cut.

## Actions
- [ ] After each laptop retest, retrieve `/dali-bootlog/current/` from the metadata partition —
  done when its snapshot and logs are reviewed for that build.

## Handoff log
- 2026-11-02 (this commit) — Reviewed the owner's laptop snapshot and logs from `95b3bf6`
  (backlight, ALSA, battery, power HAL writes, a 10 s TPM wait). The snapshot still lacks DRM
  connector and cpufreq details.
- 2026-11-02 `95b3bf6` — Snapshot waits for successful log preparation, rejects directory
  outputs and records backlight labels. Focused failures/gates and enforcing QEMU recovery pass.
  Latest physical logs remain unavailable; owner retrieval is still needed.
- 2026-11-02 `uncommitted` — 87 tests pass; image build and no-op repeat pass. QEMU on a reflinked
  copy shows setup with SELinux enforcing and creates the snapshot; physical hardware details await
  the owner's USB update and retest.
- 2026-11-02 `uncommitted` — EFI safeguard passes offline UEFI checks; the owner updated the
  USB and read-back matched. Its saved previous menu can be unsafe.
- 2026-11-01 `uncommitted` — Added an opt-in framebuffer-free menu entry; focused tests and both
  disposable UEFI shell checks pass. The USB menu and backup read back correctly; laptop test panicked.
- 2026-11-01 `uncommitted` — Added bounded native collectors, a rotation/readiness helper and
  scoped enforcing policy; 19 focused tests and three UEFI boots pass. Runtime checks caught
  and fixed the directory-rename permission; new hardware logs are next.
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
