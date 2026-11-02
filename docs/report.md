# gbos-dali report: how it works, what changed, and how it compares

Written 2026-11-02 at commit `e7f7865`, after the owner confirmed that the laptop boots quickly
with the important hardware working. The details are in the component specs
([specs/README.md](specs/README.md)) and the code; this document explains how they fit together.

## 1. Status

**Working on the MSI Modern 15 B7M** (owner report): fast boot, setup completed, Wi-Fi, keyboard,
touchpad, speaker sound (ALC256), screen brightness, AMD-accelerated desktop. App launches feel
faster than Churro and gbos-x86, but no benchmark has measured this.

**Built but not confirmed on hardware:** Bluetooth (official MT7922 firmware added after the
log showed it was missing) and the HDMI frame-rate fix.

**Not done:** internal microphone (AMD ACP), HDMI audio, suspend/resume, Vulkan app UI (HWUI),
camera, SD reader, and the remaining instruction traps in Google's signed ART/Rust code.

**QEMU:** the regression check reaches the setup screen. `sys.boot_completed` takes about 20 s
on a repeat boot.

## 2. The idea in one paragraph

Take Google's official, signed Googlebook recovery image (Android 17 desktop, build
`CL3B.260622.276.R4`) and change as little as possible so it runs on this laptop. Everything we
change is a file you can read in the repository:

- a list of files to remove;
- a list of files to add;
- a unified diff against Google's original text file;
- a kernel source patch.

No Google executable is byte-edited. The build is a normal Makefile that runs every compiler
inside a pinned Debian container. Every download is pinned by version and SHA-256. Outputs are
cached by their inputs, so an unchanged rebuild takes seconds and writes nothing.

## 3. How a build works

```
Google recovery image (read-only, RECOVERY_IMAGE in config.mk)
  └─ make unpack ─────────────► out/google/       partitions, ramdisks, inventory
GKI source + Google toolchain ► kernel bzImage + our signed modules     (make gki)
linux-firmware (pinned)       ► only the listed AMD/MT7922 files
Mesa + libdrm + NDK           ► softpipe / Zink / RADV for Android      (make mesa)
LineageOS minigbm             ► AMD gralloc                             (make minigbm)
emulator system image         ► software KeyMint/Gatekeeper, generic bionic/libz
                 │
                 ▼
android/<partition>/ remove.list, install.list, *.patch   (scripts/android-overlay.sh)
                 │   rebuild EROFS under fakeroot, check every file's bytes/mode/owner/label
                 ▼
system_a, vendor_a, system_ext_a, vendor_dlkm_a, vbmeta_a ─► out/android/disk.img (only changed ranges)
kernel + initrd + GRUB + menu ─────────────────────────────► DALI-BOOT FAT32 partition
                 │
                 ├─ make qemu / qemu-check        boot the same disk in QEMU
                 ├─ make deploy-android USB=...   copy boot files to the USB's mounted ESP
                 └─ update-os.sh (owner, local)   write changed OS partitions to the USB with read-back
```

The pieces, with the files that implement them:

| Step | What happens | Where |
|---|---|---|
| Builder | Debian container with every build tool; the host only needs Docker, make and Python. | [scripts/builder.sh](../scripts/builder.sh), [docker/Dockerfile](../docker/Dockerfile) |
| Pins | Every download: URL, version, SHA-256 or git commit, and why we use it. | [sources.mk](../sources.mk) |
| Settings | Recovery image path, CPU count, memory, data size. | [config.mk](../config.mk) |
| Unpack | Extract Google's partitions read-only and record an inventory. | [Makefile](../Makefile) `unpack` |
| Kernel | Google's GKI tag `android17-6.18-2026-06_r52`, Google's exact clang/Rust/pahole, our config fragment and patches. Exports and CRCs are checked against Google's. | [kernel/](../kernel), [specs/kernel.md](specs/kernel.md) |
| Partitions | Google's original + declared changes → EROFS; each file's metadata is checked. | [scripts/android-partition.sh](../scripts/android-partition.sh), [scripts/android-overlay.sh](../scripts/android-overlay.sh), [tools/fs_metadata.py](../tools/fs_metadata.py) |
| Replacement check | A replaced library must keep every export that something imports. A replaced APEX keeps its name, version and file list. | [scripts/check-replacements.sh](../scripts/check-replacements.sh) |
| Vendor link check | Programs we add may link only to vendor libraries or the LLNDK. | [scripts/check-vendor-libs.sh](../scripts/check-vendor-libs.sh) |
| Disk | Reflinked copy of Google's disk; userdata moved to the end and grown; blank `KERN-A` merged into a 576 MiB FAT32 `DALI-BOOT`. Created once and never recreated automatically. | [scripts/android-disk.sh](../scripts/android-disk.sh) |
| Sync | Copy only changed partitions into the disk, then read them back. Refuses while QEMU holds the disk. | [tools/android_sync.py](../tools/android_sync.py) |
| Boot files | Kernel, initrd, GRUB and menu; written into the ESP with mtools (no mounts, no root). | [scripts/android-boot.sh](../scripts/android-boot.sh), [tools/deploy.py](../tools/deploy.py), [boot/android-menu.cfg](../boot/android-menu.cfg) |
| Checks | `make test` (104 unit tests), `make qemu-check` (bounded graphical boot), `make android-uefi-check` (UEFI/GRUB boot from a temporary USB image next to a decoy NVMe). | [tests/](../tests), [tools/android_smoke.py](../tools/android_smoke.py), [tools/android_uefi_test.py](../tools/android_uefi_test.py) |

**Build speed:**

| Change | Time |
|---|---|
| Nothing changed (`make android-image`) | about 16 s; nothing written |
| One partition changed | under 1 min |
| Kernel config edit | about 75 s relink |
| New kernel source tree | about 1 h (first build) |

**Updating the laptop:**

1. Run `make android-image`.
2. Run `make deploy-android USB=/run/media/$USER/DALI-BOOT`. This step updates the boot files and
   keeps the previous build's files.
3. Run `sudo bash out/usb-flash-android/update-os.sh`. The script checks the approved USB's
   by-id identity and its layout, writes only the OS partitions that changed, and reads each one
   back. It never touches userdata or metadata.

## 4. What we change in Google's image

These directories are the complete record: [android/system/](../android/system),
[android/system_ext/](../android/system_ext), [android/vendor/](../android/vendor),
[android/vendor_dlkm/](../android/vendor_dlkm), [android/module_ramdisk/](../android/module_ramdisk),
plus [android/cmdline.txt](../android/cmdline.txt) and [android/bootconfig.txt](../android/bootconfig.txt).
`make test` fails if any file in them is unused.

### Removed

| What | Why |
|---|---|
| update_engine, OTA | Google's updates expect Google's hardware and partitions. |
| Firmware updaters (flashrom, futility, fwupd, gscutil, …), charge control, the real `crossystem` | Never let Google's tools write this laptop's firmware. Removing `gscutil.rc` also removed a 10 s wait for `/dev/tpm0` on every boot. |
| Trusty VM launcher; Trusty, Weaver, Secretkeeper, OEM-lock, remote key provisioning and StrongBox HAL declarations | The hardware does not exist; Android waits for it or keeps retrying. |
| Face HAL APEX | No face sensor. FaceService otherwise polled for a test HAL once a second. |
| timberslide | Chromebook EC log collector; there is no EC. |
| Panther Lake bionic, libz and runtime APEX libraries | Built with GFNI/AVX-VNNI. On Zen 3 every such instruction traps to the kernel emulator. |
| Vendor's precompiled SELinux policy | Lets the platform compile policy that includes our two logging domains. SELinux stays enforcing. |

### Added

| What | Why |
|---|---|
| Generic bionic/libz/runtime from the pinned Android 17 emulator image | Same API, plain x86-64. QEMU traps fell from 15.3 M to 44,644 (99.7% fewer). |
| Software KeyMint and Gatekeeper from the emulator image, bytes unchanged | Replace Trusty/GSC; lock screen and file encryption work. |
| Mesa (softpipe, Zink, RADV), minigbm, pinned firmware | Graphics on AMD and in QEMU; Wi-Fi/BT firmware. |
| Our signed kernel modules in vendor_dlkm (amdgpu, mt7921e/mt76, …) | Drivers Google does not ship. |
| `crossystem` stand-in ([crossystem-qemu.c](../android/crossystem-qemu.c)) | The boot HAL calls it; it accepts only the success values and rejects everything else. |
| [no-face.xml](../android/vendor/no-face.xml) | Declares that there is no face feature. |
| `get_variant_audio` and [audio-msi.rc](../android/vendor/audio-msi.rc) | Rename the ALC256 card to the ID Google's audio HAL expects, then restart the HAL. |
| [dali.rc](../android/system_ext/dali.rc), `graphics-*.rc` | Disable gscd/udsattestation; choose the graphics profile from the GRUB argument. |
| [bootlog.rc](../android/system_ext/bootlog.rc) and helpers | Save kernel and Android logs plus a read-only hardware snapshot to `/metadata/dali-bootlog`. |

### Patched (unified diffs of Google's text files)

| Patch | Change |
|---|---|
| vendor `audio-msi`, `audio-policy` | ALC256 mixer paths: speaker, headphone and mic on analog PCM 0. |
| vendor `build-prop` | Graphics profile properties; gamma log spam fix. |
| vendor `file-contexts` | SELinux labels for DRM, GPU sysfs, the sound card ID and the backlight. |
| vendor `powerhint` | Drop the 8-CPU masks that confined apps to CPUs 0–7 and media to 4–7. |
| vendor `ueventd` | Serialize uevents. |
| vendor_dlkm `modules` | Allow `snd_hda_intel`; preload the ALC256/HDMI codecs. |
| module_ramdisk `modules` | QEMU virtio drivers (Google's prebuilt modules). |
| system_ext `vintf-manifest` | Remove the HAL declarations listed above. |

**Kernel command line** ([cmdline.txt](../android/cmdline.txt)):

- Google's arguments, minus the Intel-only ones and the SPI-flash write enables.
- Plus a TPM/SPI-flash driver blacklist and `efi_pstore.pstore_disable=1`.
- `console=null` is dropped.
- The laptop's GRUB entry adds `console=drm_log`, `initcall_blacklist=nvme_init` (the internal
  disk stays hidden), `mt7921_common.disable_clc=1` and `androidboot.dali.graphics=amd`.

**Bootconfig:** slot A, orange/unlocked verified boot, external boot source, StrongBox off.
vbmeta is regenerated by `avbtool` with verification disabled.

## 5. Kernel

Google's GKI 6.18 is built from source. Google's prebuilt kernel cannot be used because Churro's
[vex-emulate](../sources.mk) instruction emulator must be compiled in: Google's userspace uses
Intel instructions that Zen 3 lacks.

- **ABI kept exactly.** The build uses Google's compiler, keeps Google's release string, every
  export and CRC, `TRIM_UNUSED_KSYMS` and Google's certificate. Google's own modules load
  unchanged, and the build fails on any difference.
- **Our modules** are signed with the build's own key ([laptop-modules.list](../kernel/laptop-modules.list)).
  vendor_dlkm uses Zstd so they fit without resizing anything.
- **Config fragment** ([gki.config](../kernel/gki.config)): trusted key, touchpad, simpledrm and
  drm_log, modular amdgpu, EROFS Zstd. Unlisted config changes fail the build.
- **Patches:**
  - [drm-firmware-handoff.patch](../kernel/drm-firmware-handoff.patch) (from Churro): release the
    firmware framebuffer before amdgpu takes a DRM minor.
  - [msi-backlight.patch](../kernel/msi-backlight.patch): on this exact DMI model only, name the
    first panel `backlight` so Google's unchanged lights HAL finds it.
  - [amdgpu-fast-flips.patch](../kernel/amdgpu-fast-flips.patch): on DCN < 3.2, do a full update
    only when a CRTC really needs a modeset. This fixes the halved frame rate with HDMI and is
    small enough to upstream.

## 6. Graphics

GRUB detects the Barcelo GPU (PCI `1002:15e7`) and passes `androidboot.dali.graphics=amd`.
Without that GPU it selects softpipe.

| | AMD laptop | QEMU |
|---|---|---|
| App UI (HWUI) | Skia GL on ANGLE → Zink → RADV | Skia GL, Mesa softpipe |
| SurfaceFlinger | Skia Vulkan (threaded) on RADV | GL, softpipe |
| Buffers | minigbm + Mesa GBM (Zink) | same |
| Density | 160 | 240 |
| Boot animation, shader priming | Google's | skipped (saves about 27 s of software rendering) |

- **Mesa:** 26.3.0-rc3, built with NDK r30 for API 35 and no LLVM (RADV uses ACO). libdrm and
  expat are linked statically.
- **Mesa patch:** [mesa-drm-master.patch](../android/mesa-drm-master.patch) drops DRM master so
  the composer can drive the display.
- **minigbm:** LineageOS minigbm with [minigbm-amd.patch](../android/minigbm-amd.patch). An ABI
  gate ([minigbm_abi.py](../tools/minigbm_abi.py)) checks it.
- **Vulkan HWUI is shelved.** Android needs two graphics queues and RADV exposes one. A draft
  adapted from Churro's earlier RADV queue patch is kept outside the repository.

## 7. Security model

- **Development device, not a secure one.**
  - KeyMint and Gatekeeper are software implementations, so there are no hardware-backed keys,
    attestation or rollback resistance.
  - Verified boot is orange/unlocked.
  - Play Integrity and Google sign-in limits are untested.
- **What is kept:**
  - SELinux is enforcing. Our two new domains (log collection, hardware snapshot) are narrow.
    The audio helper may write only the ALC256 card-ID file, through its own label. There are no
    permissive domains.
  - Google's own signed binaries run unmodified.
- **Firmware safety:**
  - Firmware updaters are removed.
  - TPM and SPI-flash drivers are blacklisted.
  - EFI pstore is disabled.
  - The internal NVMe is hidden from Android.

## 8. Diagnostics

- Logcat collectors save the kernel log, the Android log and a startup-only `android-boot.log`
  to `/metadata/dali-bootlog/{current,previous}`. Each stream rotates within a fixed budget.
- After boot, a one-shot, read-only snapshot records:
  - backlight, ALSA and module state;
  - DRM connectors;
  - cpufreq settings.
- Read the logs from Linux with `debugfs` on the metadata partition. This works because metadata
  is not encrypted.
- GRUB has a debug entry with `earlycon=efifb`. It is not the default because it costs about a
  minute per boot.

## 9. Performance fixes and measurements

| Fix | Effect | Evidence |
|---|---|---|
| `earlycon=efifb` moved to the debug entry | Laptop boot was 104 s, 60.8 s of it in synchronous early console output | [laptop-hardware.md](specs/laptop-hardware.md) |
| `gscutil.rc` removed | −10 s TPM wait on every boot | [security.md](specs/security.md) |
| Generic bionic/libz | 99.7% fewer instruction traps (QEMU) | [os-image.md](specs/os-image.md) |
| Power HAL CPU masks dropped | Apps get all 12 CPUs, not 0–7; media is no longer stuck on 4–7 | [laptop-hardware.md](specs/laptop-hardware.md) |
| amdgpu fast flips | Fixes the halved frame rate with HDMI (hardware confirmation pending) | [kernel.md](specs/kernel.md) |
| Face polling, udsattestation, gamma log | Remove once-a-second wakeups and log spam | [security.md](specs/security.md) |
| QEMU: no boot animation or shader priming | `boot_completed` 49 s → 20–22 s | [qemu.md](specs/qemu.md) |
| Incremental build | Unchanged rebuild about 16 s, zero writes | [os-image.md](specs/os-image.md) |

Churro and gbos-x86 have none of these fixes, except that gbos-x86 also disables udsattestation.

The laptop's kernel log still shows instruction traps (about 150–200 per log file). They come
from Google's signed ART/Rust code, which we cannot replace with generic builds.

## 10. The reference projects

Both references are in [reference/](../reference). Both boot Googlebook OS on this laptop. We took
working ideas from both, Churro most of all, and rebuilt them in a form that is easier to read and
safer to run.

### Churro (`project-churro-msi-modern-15-B7M`)

- **Pipeline:**
  - `sudo ./churro.sh auto <recovery.bin> <out.img>` loop-mounts the image as root.
  - `tools/prepare.sh` reads the kernel identity from the image and downloads the matching GKI
    source and toolchain from Google's manifest.
  - The kernel, modules and Mesa are cached under `/var/cache/churro` by cache keys.
  - Partitions are repacked in full on every build; `--no-repack` skips this.
  - `install` uses `dd` to write a whole disk after you type `YES`.
- **Changes to Google's image:** 16 feature directories (`features/*`), each with
  `patch-<partition>.sh` shell scripts plus files, rc files, CIL policy and cmdline fragments.
  Text is changed by `sed` inside those scripts. Binaries are replaced or built, not byte-edited.
- **Kernel:** the same GKI rebuild with CRC checks against Google's `vmlinux.symvers`, but module
  signature enforcement and `TRIM_UNUSED_KSYMS` are turned off. Distro module options are
  imported selectively.
  - The 16 patches include `vex-emulate` (23 instructions) and `drm-remove-firmware-fb`.
  - Most of the rest are for Nouveau and Intel hardware we do not have.
- **Graphics:**
  - Mesa 26.3.0-rc3 with iris, crocus, nouveau, zink, virgl, softpipe, NVK, hasvk and RADV.
  - Its AMD profile (`gfx-amdgpu.rc`) is the one we copied: ANGLE + Zink for GL, RADV
    `skiavkthreaded` for SurfaceFlinger, GL HWUI.
  - Density 180.
- **Hardware:** generic Intel/AMD/NVIDIA coverage. Audio is generated ALSA configs for several
  card types, bind-mounted, plus a C mixer (`churro-mixer`). Wi-Fi/BT use the linux-firmware
  "extra" pack. There is no MSI-specific backlight work.
- **Security:** emulator KeyMint/Gatekeeper (SHA-1 pinned), firmware lockdown, no root.
- **Quality:**
  - Readable, heavily commented shell organized by feature.
  - The build runs as root with loop devices.
  - Some downloads are versioned but not SHA-256 verified, and the recovery image is not pinned.
  - No unit-test suite; there are QEMU and GBM tests.

### gbos-x86 (`gbos-x86-msi-modern-15-B7M`)

- **Pipeline:**
  - `./build.sh` downloads Google's recovery zip, pinned by SHA-256.
  - Six logical partitions are extracted and combined into a `super.img` stored on a FAT32 USB
    partition.
  - A custom kernel (`6.18.21-gbos-whl`) boots a busybox "stage0" initramfs. Stage0 loop-mounts
    the partitions and then runs Google's init with a hook layer.
  - Docker volumes hold sources. There is a full installer (NVMe/eMMC/SATA, dual boot, Windows
    boot entry).
- **Changes to Google's image:** mostly done at runtime by bind mounts from the USB rather than
  by rebuilding partitions.
  - **Byte-patched Google binaries:** libz, libcrypto (SHA-NI redirected), KeyMint compat,
    minigbm/gralloc. They live in `usb/patched/` and are created by `tools/*.py` patchers.
  - Patch sites are located by symbol or byte pattern.
  - Each replacement is hash-gated: it is bound only if the mounted original has the expected
    SHA-256, so a new Google build fails closed.
- **Kernel:** not ABI-compatible with Google's GKI. It builds its own modules and uses a different
  release string.
  - Patches: an ISA emulator, an ashmem shim, i915 color/gamma fixes, Surface and HP quirks, and
    a debug SELinux config.
  - KernelSU v3.3.1 is built in.
  - It ships a broad firmware/SOF tree and runtime modalias hot-plugging (`hwdetect.sh`).
- **Graphics on the MSI:** SwiftShader fallback, or an experimental RADV build (Mesa at a
  commit, AMD Vulkan only) bound over `vulkan.intel.so`. Its documentation reports a red-square
  pointer, broken HEVC and the touchpad not confirmed on the MSI. Default density 260;
  `RESOLUTION=2400x1350` is documented for the MSI.
- **Hardware:** broad and generic (Intel focus, plus Surface and HP). The MSI is its only AMD
  machine and is marked experimental.
- **Security:** software Gatekeeper (`soft_gk`), patched KeyMint compatibility library, KernelSU
  root, and a debug SELinux option.
- **Quality:**
  - Excellent documentation and real tests (QEMU installer and emulator tests).
  - The repository carries large firmware and module payloads and prebuilt modified binaries.
  - The boot path is a parallel system beside Google's: its own initramfs, loop mounts and binds.

### Side by side

| | Churro | gbos-x86 | gbos-dali (ours) |
|---|---|---|---|
| Entry point | `sudo churro.sh` | `build.sh` + Docker | `make` + Debian container |
| Needs root to build | yes (loop mounts) | partly (Docker) | no (fakeroot, mtools) |
| Download pinning | versions; some SHA-1, some unchecked | recovery SHA-256, commits | everything SHA-256 or commit, in one file |
| Incremental build | cache keys; full repack | super/partition reuse | per-partition Make dependencies; no-op build writes nothing |
| Google's image changed by | shell scripts using `sed` per feature | runtime bind mounts + byte patches | remove/install lists + `diff -u` patches |
| Binary edits | none | yes, hash-gated | none |
| Kernel | GKI rebuild, CRCs kept, signing off | own kernel + KernelSU | GKI rebuild, CRCs, signing and trimming kept |
| Boot path | Google's boot flow + GRUB | own stage0 initramfs | Google's ramdisks + GRUB |
| Hardware scope | broad (Intel/AMD/NVIDIA) | broad (Intel, Surface, HP; AMD experimental) | this laptop + QEMU |
| MSI graphics | ANGLE/Zink/RADV | SwiftShader or experimental RADV | ANGLE/Zink/RADV (Churro's profile) + HDMI flip fix |
| MSI audio | generic generated configs | generic HDA configs | Google's HAL + ALC256 XML from measured controls |
| MSI backlight | not specific | ACPI generic | DMI-limited kernel rename; works |
| Root | no | KernelSU | no (out of scope) |
| Installer | `dd` whole disk | full installer, dual boot | none; boots from USB |
| Tests | QEMU, GBM, vexemu | QEMU, installer, patchers | 104 unit tests, QEMU, UEFI/USB check |

### Where we are better

1. **Readable change record.** Every change to Google's image is a list entry or a `diff -u`
   with a header that says why. There is no `sed` in scripts and no byte patching. A reviewer can
   read [android/](../android) and know exactly what differs from Google.
2. **Safer to build and deploy.**
   - The build needs no root, no loop devices and no raw disk writes.
   - The USB update writes only changed OS ranges, checks the device identity and reads back.
   - Data and metadata are never written.
3. **Kept Google's kernel ABI and module signing.** Google's modules load unchanged and our
   modules are signed. Churro turns enforcement off; gbos-x86 replaces the kernel.
4. **Faster repeat builds**, measured above. Churro repacks every partition on every build.
5. **Fixes that neither reference has:**
   - the 10 s TPM wait;
   - the power HAL CPU masks;
   - face polling and the gamma log spam;
   - the HDMI flip regression;
   - the early-console minute;
   - the drop-in checks for replaced libraries.
6. **Tailored, not generic.** We removed broad-hardware machinery: Nouveau and Intel patches,
   generated audio configs for many card types, the installer, and runtime hot-plugging.

### Where we are behind

| Gap | Who has it | Comment |
|---|---|---|
| Vulkan HWUI | Churro had a RADV two-queue patch | Draft saved; needs testing. Possible app-UI speed gain. |
| Internal mic (ACP DMIC), HDMI audio | Churro generates DMIC/HDMI routes | Next audio step. |
| Fewer instruction traps | gbos-x86 redirects SHA-NI/Adler in libcrypto/libz | Only with binary patches, which we refuse; our generic-library swap covers libz/bionic. Measure the remaining traps first. |
| Installer, internal-disk boot | both | Out of scope for now; the USB works. |
| Root (KernelSU) | gbos-x86 | Out of scope unless you ask. |
| Software Gatekeeper on unsupported Google builds | gbos-x86 `soft_gk` | Not needed: the emulator's Gatekeeper works. |
| Pinned Google recovery input | gbos-x86 pins the zip SHA-256 | We read a local image. Pinning its hash in [config.mk](../config.mk) would be a cheap improvement. |
| Hardware detection report | gbos-x86 `hwdetect.sh` | Our post-boot snapshot covers the useful part for one laptop. |

### Ideas worth considering (not approved; each needs your agreement)

1. Pin the recovery image's SHA-256 next to `RECOVERY_IMAGE` so a different Google build fails
   early with a clear message.
2. Test Vulkan HWUI with the saved RADV two-queue draft, behind a GRUB option, and compare the
   frame rate with the current GL HWUI.
3. Add AMD ACP DMIC and HDMI audio routes, following the measured-control approach used for
   ALC256.
4. Count the remaining instruction traps on the laptop by instruction and by binary. Fix them only
   if they cost real time.
5. Send the amdgpu fast-flip fix and the Google lights-HAL backlight finding upstream.

## 11. Next steps

1. **On the laptop:**
   - Confirm Bluetooth pairing and the HDMI frame rate.
   - Compare the AMD boot-animation time (`boot_progress_enable_screen` vs `sf_stop_bootanim` in
     the saved logs).
2. **Then:** microphone, HDMI audio and suspend, one at a time, each tracked in
   [specs/laptop-hardware.md](specs/laptop-hardware.md).
3. **Keep the baseline safe:** always run `make test` and `make qemu-check` before updating the USB.
