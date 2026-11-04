# Boot chain

**Status:** partial — opt-in diagnostics and default Berberis selection verified in QEMU;
physical retest pending.
**Last verified:** 2026-11-04 — 67 focused deploy/boot/menu tests pass;
`grub-script-check` and `make android-uefi-check` pass. Disposable UEFI boots confirm
Berberis default and Houdini override both reach Android and persist the selected entry in the
ESP-root environment block. Physical menu selection remains unverified; Houdini's failure cause
is unknown.
Earlier, 57 focused boot/logging/overlay tests pass. Image rebuild changes only system_ext and
boot files; repeat preserves published timestamps and writes nothing. Direct diagnostic boot
saves fresh streams/snapshot; normal boot leaves saved bytes and inode timestamps unchanged.
Actual diagnostic GRUB entry boots under enforcing UEFI/QEMU, with NVMe decoy unchanged. Setup
and injected-tap Accessibility screenshots inspected; no project-domain denials.
[Evidence](../../out/optin-logs/). Physical retest/performance unmeasured.

Earlier, 2026-11-04 — Rename: 246 tests and enforcing direct/UEFI QEMU pass.
Setup and Accessibility after an injected tap are inspected. New collector domains, saved
boot/snapshot logs, serial identity and optional Berberis argument are checked, with no
project-domain denials. Old disks preserved; physical retest pending.
[Evidence](../../out/gbos-builder-validation/).

Earlier, 2026-11-02 — 53 focused tests pass; the image rebuild changed only system
and system_ext, with metadata verified. A repeat preserves image/bundle timestamps and writes
no partitions. Two enforcing UEFI/QEMU runs reached inspected setup screens, selected Houdini
then Berberis, persisted bridge identity and controlled fatal records, and retained the previous
crash stream. The hidden NVMe decoy stayed unchanged
([results](../../out/arm-translation-diagnostic/verification-final.log)).
The same NDK-built ARM64 executable traps inside Houdini (`SIGTRAP`, `libhoudini.so+0x321bec`)
but prints its success marker under Berberis. This tests executable translation, not an ARM
app's ART/JNI or graphics path. The owner subsequently updated the USB and reports the previously
failing game, another native app and Hearthstone work on the laptop with Berberis. No new laptop
logs were retrieved; Houdini's internal failure cause and broader app compatibility remain unknown.
Earlier, the laptop's `95b3bf6` kernel log shows `earlycon=efifb` drawing
686 early lines at 89 ms each: 60.8 s of its 104 s to `boot_completed`
([summary](../../out/earlycon-validation/summary.txt)). The normal entry now omits it;
`make android-uefi-check` passed, the early [screen](../../out/earlycon-validation/uefi-early-screen.png)
still shows the kernel's drm_log and the graphical run reached [setup](../../out/earlycon-validation/uefi-setup-screen.png).
The laptop's shorter boot is not yet measured.
Before that, an enforcing 12-vCPU QEMU boot kept the whole startup in
`android-boot.log*`: 25,419 entries (4,010,284 bytes, no archive dropped) from logd's first
entry to boot completion, after which the copy stopped; no `dali_*` denials (pre-rename)
([summary](../../out/boot-window-log-validation/summary.txt)). `make qemu-check` passed
and its setup [screen](../../out/boot-window-log-validation/screen.png) was inspected.
Before that, the snapshot gained display connectors and cpufreq
policies. An enforcing 12-vCPU QEMU boot recorded the virtual connector's status and modes, the
service exited 0 with no `dali_hardware_diag` denials (pre-rename), and QEMU correctly shows no cpufreq
([snapshot](../../out/snapshot-display-cpu-validation/hardware.txt),
[service](../../out/snapshot-display-cpu-validation/service.txt)); `make qemu-check`
passed and its setup [screen](../../out/snapshot-display-cpu-validation/screen.png) was inspected.
Before that, the owner retrieved the laptop's `/dali-bootlog/current/` from
its `95b3bf6` boot ([snapshot](../../out/laptop-boot-2026-11-02-hdmi/current/hardware.txt)): it
records the eDP `backlight` device and labels, ALC256 on card1 and the loaded HDA modules.
Before that, a readiness-gated snapshot was recovered from a disposable enforcing
QEMU boot ([snapshot](../../out/hardware-fixes-validation/final-production-hardware.txt)).
It exits successfully and does not run before boot-log preparation succeeds.
Earlier, `make test` passed 87 tests; `make android-image` rebuilt
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
Verified: gbos-builder clean-break rename aligns GRUB arguments, Android imports,
services, readiness property and diagnostic paths. `gbos_builder` is used for properties and
SELinux identifiers; filesystem paths use `gbos-builder`. Old saved evidence is retained under
its original names. No compatibility with previous Dali boot media. Fresh-image and saved-log
checks pass; hardware-only services still need physical retesting.

Verified: initrd = Google platform ramdisk + Google module ramdisk extended with our virtio
modules + Google generic ramdisk + bootconfig; slot A boots normally; first-stage mounts succeed.
Also verified through OVMF/GRUB on disposable USB disks for the normal and framebuffer-free
entries. The early-console debug entry was not booted; it differs only by `earlycon=efifb`,
which the normal entry used until this change.
The normal physical boot completed setup on the AMD desktop with working Wi-Fi, keyboard and
touchpad. Actual GPU acceleration remains unverified. The framebuffer-free test reached
Android early-init and panicked; its metadata logs are from the earlier boot.
Native logcat collectors now save kernel/init and Android logs under `/metadata/gbos-builder-bootlog/`.
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
It also records DRM connector status/modes and each cpufreq policy's driver, governor, EPP and
limits; Google's base policy already lets every domain read the cpufreq files.
`android.log` rolls within about a minute of boot, so a third collector writes
`android-boot.log*` until boot completes; QEMU's startup took 4.0 MB of its 8 MiB.

Previously verified in QEMU: the Berberis ARM64 test entry and independent `crash.log*` collector.
The entry used Google's existing `libndk_translation.so` and its ARM64-library/executable-
registration init hooks. `boot.txt` records the selected bridge. The default now selects
Berberis in direct QEMU; laptop selection has not yet been retested.
Before the switch, the owner reported Besiege closing back to the desktop and many other apps
failing. The retrieved
[logs](../../out/laptop-boot-2026-11-02-apps/dali-bootlog/current/) retain only about ten seconds
of rolling Android output, flooded by game-session/focus transitions; no fatal signature was
retained. A small ARM64 executable traps in Houdini but runs in Berberis in QEMU. The owner
subsequently confirms the previously failing game, another native app and Hearthstone work with
Berberis on the laptop. This supports a translator-compatibility problem, not a proven internal
cause; the game-controls loop was not established as the cause.

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
- GRUB detects the MSI's PCI `1002:15e7` and passes `androidboot.gbos_builder.graphics=amd`.
  Otherwise it selects softpipe; Android's shared init file imports the matching profile.
  AMD modules load by PCI alias from vendor_dlkm after vendor firmware is available, not
  from the first-stage module ramdisk.
- A separate, non-default GRUB entry tests `initcall_blacklist=sysfb_init` without removing the
  NVMe blacklist. It is an experiment, not a proven display fix.
- `earlycon=efifb` is only in a separate debug entry, as in Churro: it prints synchronously and
  cost the laptop a minute per boot. The normal entry's screen log starts with simpledrm.
- Persistent diagnostics use Google's logcat and `ro.logd.kernel=true`, not a custom logger.
  They are opt-in per boot: the GRUB diagnostic entry passes `androidboot.gbos_builder.logs=1`.
  Without it, no project collectors, preparation/rotation or hardware snapshot run, and saved
  records remain untouched. Normal Android in-memory logging stays available.
  Direct QEMU validation explicitly passes `--diagnostic-logs`; ordinary `make qemu` does not.
  The owner approved a dedicated enforcing domain, a small rotation/readiness helper and
  Linux retrieval from unencrypted metadata. Only current/previous diagnostic boots are retained.
  Each stream rotates at 256 KiB with seven archives, leaving headroom below the agreed
  16 MiB per stream per boot and space for other files on the 64 MiB metadata partition.
  A third copy, `android-boot.log`, rotates at 1 MiB (8 MiB total) and stops at boot completion,
  because startup alone overflows the 2 MiB `android.log`.
  A crash-buffer-only copy, `crash.log`, rotates at 256 KiB (2 MiB total) and remains running
  after boot, so desktop transition spam cannot evict fatal records. All four streams together
  budget 14 MiB per boot, plus record-size overshoot and the small snapshots.
  Collection begins at `post-fs`, not first-stage init; an earlier hang still needs a photo.
- Use Google's bundled Berberis (`libndk_translation.so`) as the default native bridge; retain
  Houdini in the image. GRUB offers both choices and persists the selected entry in the ESP-root
  `grubenv`, outside the directories replaced by boot updates. A missing environment block starts
  with Berberis; selecting the other translator changes the next-boot default, not just the current
  boot. Diagnostic and experimental entries use Berberis without changing that saved choice;
  failed translator boots do not reset it. Early-init sets the read-only bridge property before
  zygote, with an optional `androidboot.gbos_builder.native_bridge` kernel argument for another
  bootloader. The reason some apps fail under Houdini remains unknown; use Google's existing
  translator hooks unchanged. No new security permissions.
- A one-shot diagnostic gated by both `sys.boot_completed=1` and `sys.gbos_builder.bootlog.ready=1`
  may read backlight, ALSA and loaded-module metadata
  into the current boot log directory. It must not read sound device nodes or write sysfs, and it
  uses a separate enforcing SELinux domain.

## Files
- [android/cmdline.txt](../../android/cmdline.txt) — one argument per line, with reasons.
- [native-bridge.patch](../../android/system/native-bridge.patch) and
  [gbos-builder.rc](../../android/system_ext/gbos-builder.rc) — let early-init select the native bridge.
- [boot/android-menu.cfg](../../boot/android-menu.cfg) — laptop GRUB menu and persistent translator choice; the direct-kernel VM does not use it.
- [tools/deploy.py](../../tools/deploy.py) — seeds a missing ESP-root `grubenv` with Berberis and preserves an existing selection.
- [scripts/android-boot.sh](../../scripts/android-boot.sh) — preserves the saved choice while replacing managed boot directories.
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
`make android-initrd`, then `make qemu-check`. Kernel and init log: `out/qemu/kernel.log`.
To recheck EFI pstore without hardware writes, run the
[validation driver](../../out/efi-pstore-validation/check.py):
`scripts/builder.sh python3 out/efi-pstore-validation/check.py out/efi-pstore-validation/NEW-RUN`.
Use a new evidence directory; the unguarded control runs only in an offline disposable guest.
Focused tests: `scripts/builder.sh python3 -m unittest discover -s tests -p test_bootlog.py -v`
and the same command with `test_overlay.py`. Rebuild with `make android-image`.
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
- `earlycon=efifb` draws and scrolls every early kernel line on the uncached firmware framebuffer
  before the kernel continues (89 ms per line on the laptop). Disposable UEFI checks add a serial
  console, which disables it, so QEMU never shows this cost.
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
- [ ] After each laptop retest, retrieve `/gbos-builder-bootlog/current/` from the metadata partition —
  done when its snapshot and logs are reviewed for that build.

## Handoff log
- 2026-11-05 (this commit) — `deploy.py` now knows only the Android bundle; its mounted-USB
  `usb` command went with `make deploy-android`. A stick with the old diagnostic marker is
  refused without writes. The Android marker bytes are unchanged, so existing USBs still update.
- 2026-11-04 (this commit) — Explain how GRUB selects and remembers the translator, including how
  diagnostic/experimental entries and failed boots affect the saved choice.
- 2026-11-04 (this commit) — Add persistent Berberis/Houdini selection in ESP-root `grubenv`;
  updates preserve the choice. 67 focused tests and disposable UEFI boots validate both options
  and saved state. Physical selection remains untested.
- 2026-11-04 (this commit) — Make Berberis the default and remove its translator-specific GRUB
  entry. Four focused tests, QEMU smoke check and direct property query pass; laptop retest and
  Houdini failure cause remain unknown.
- 2026-11-04 (this commit) — Persistent capture is opt-in through the diagnostic GRUB entry.
  57 tests, enforcing direct/UEFI boots and no-write repeat pass; normal boot preserves saved
  bytes/inodes. Recovery docs/AI skill updated; physical retest remains.
- 2026-11-04 (this commit) — Lenovo post-update logs retain normal collectors and no
  `touchpad.log`; temporary input capture retirement confirmed on hardware.
- 2026-11-04 uncommitted — Removed the temporary touchpad service/script/input policy.
  50 focused tests, image rebuild and inspected enforcing QEMU pass; hardware retest pending.
  Native logs and older-capture retrieval remain. FAT32 export is discussed, not implemented.
- 2026-11-04 (this commit) — Rename arguments, services, readiness gate and log directory.
  Regenerate source-derived SELinux patches with unchanged permissions. Enforcing direct/UEFI,
  saved logs, input response and optional Berberis selection pass; no physical retest.
- 2026-11-02 (this commit) — Added opt-in Berberis boot selection, preserved Houdini default,
  and isolated crash capture. 53 tests, image/no-op rebuild and two enforcing UEFI runs pass.
  Owner confirms the failing game, another native app and Hearthstone now work with Berberis.
- 2026-11-02 (this commit) — Normal laptop entry drops `earlycon=efifb` (60.8 s of the `95b3bf6`
  boot); it moved to a debug entry. 104 tests and both UEFI checks pass; the laptop's new boot
  time awaits the owner's boot-file update.
- 2026-11-02 `43b21ac` — `android-boot.log` keeps the whole startup: in enforcing QEMU it held
  25,419 entries (4.0 MB, no rotation loss) from logd's first entry to boot completion, then
  stopped. `android.log` alone had lost them within a minute.
- 2026-11-02 `e51523d` — Snapshot adds display connectors and cpufreq policies (to answer the
  HDMI and governor/EPP questions). 104 tests, image rebuild (system_ext only) and enforcing QEMU
  pass; laptop output awaits the owner's next retest.
- 2026-11-02 `0ff3e8a` — Reviewed the owner's laptop snapshot and logs from `95b3bf6`
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
