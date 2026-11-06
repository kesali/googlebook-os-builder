# Build and deployment guide

Detailed build, hardware recipe, USB deployment and QEMU notes. Start with the
[README](../README.md) for the quick workflow and current hardware status.

## Older media and the rename

gbos-builder is a clean-break rename from gbos-dali. New boot media use `GBOS-BOOT`,
`/gbos-builder/` and `gbos-builder-*-v1` markers; Android custom properties and SELinux types
use `gbos_builder`. Existing Dali media are not update targets: the owner must explicitly
flash a new image (erasing that USB) rather than use the updater. No automatic migration is
provided. The compact private image is versioned by the pinned Ruby recovery build, currently
`out/gbos-builder/ruby-16693588/compact/disk.img`; older images and saved logs remain in place.
The recovery image's EFI-SYSTEM UUID is embedded in the initrd. When a recovery update changes
that UUID, the new image needs a fresh USB install; the updater refuses mismatched GPTs.
Reinstalling erases the selected USB's data. Reuse an existing builder with
`docker tag gbos-dali-builder gbos-builder`.
The renamed combined image is owner-confirmed on both MSI and Lenovo.

## Build and boot

For Googlebook OS, Linux needs Docker, GNU make, Python 3, `/dev/kvm` and a VNC viewer.
Allow at least 50 GB for sources, builds and recovery images, plus Android's sparse data partition.
The first build downloads Google's pinned Ruby recovery (7.8 GB ZIP, 19 GB extracted) into
`out/downloads/`. `make recovery` fetches just that
source; the extracted image must match the existing SHA-256 pin before it is published.

```sh
make qemu         # build changed components and run; VNC viewer: localhost:5900
make console COMMAND='getprop sys.boot_completed'   # from another terminal
make qemu-check   # bounded graphical check; shuts only the VM down afterwards
```

`QEMU_VNC_PORT=5901` changes the localhost-only published port. Android has 4 virtual CPUs,
6 GB RAM and a 1280x720 software-rendered display by default. Softpipe is a correctness baseline,
**not accelerated graphics**; CPU instruction emulation is another performance cost. Measure build
iteration and guest responsiveness separately; the graphics path is a runtime-performance question.

### Hardware recipes

The default image still includes both laptops. [drivers.list](../hardware/drivers.list) selects
reusable driver recipes; [devices.list](../hardware/devices.list) selects the
[MSI](../hardware/msi-modern-15-b7m/) and [Lenovo](../hardware/lenovo-e50-80/) configuration.
Shared security, logging, native translation and storage safeguards stay under [android/](../android/).
The refactoring passes 263 tests, exact baseline declaration/patch comparisons, image checks
and inspected enforcing direct/USB-UEFI QEMU boots with input. All 38 tracked output hashes
match the rename baseline; the 23.8 s repeat preserves timestamps and writes nothing.
The owner subsequently confirmed both laptops, including the latest shared audio regression
on the MSI. [Refactor evidence](../out/full-hardware-recipes/).

Recipes contain only the native files they need:

Config-only support stays in the shared [kernel config](../kernel/gki.config), grouped with
short reasons, rather than a directory for a handful of options. Device-only settings belong
to the laptop recipe. Dedicated driver recipes are useful when support also needs patches,
firmware, module packaging or tests; a source patch is not required.

| Fragment | Purpose |
|---|---|
| `kernel.mk`, `mesa.mk`, `minigbm.mk` | Explicit, ordered source patches appended to component lists |
| `gki.config`, `modules.list`, `aliases` | Kernel options, source module paths and verified hotplug aliases |
| `firmware.list` | Runtime blobs from the unchanged archive pin in [sources.mk](../sources.mk) |
| `<partition>.install`, `<partition>.remove` | Existing five-column installs and whole-file removals |
| `<partition>.patches`, `<partition>-<group>.patches` | Ordered source-derived Android text patches |

[hardware/kernel.mk](../hardware/kernel.mk) collects selected component fragments automatically.
The base lists use explicit `# recipe: name/file` includes to preserve installation and Android
patch ordering. Recipe-local install sources start with `./` and are relative to that recipe;
for example, [Lenovo's IDC declaration](../hardware/lenovo-e50-80/vendor.install).
Android patch lists name files relative to the recipe. A stray patch is never auto-selected.

The [recipe reader](../tools/hardware_recipes.py) expands declarations into temporary inputs;
it never generates Google text edits. Existing runners apply the patches with exact context
and preserve metadata, signing and ABI checks. Kernel/Mesa/minigbm source-cache keys remain
content-based: moving an unchanged patch must not replace an editable source tree.
The separate instruction-emulation patch belongs to [cpu-vex](../hardware/drivers/cpu-vex/);
this source pipeline currently requires it.

The combined [module metadata patch](../hardware/drivers/laptop-modules/vendor_dlkm/modules.patch)
is intentionally intact in `laptop-modules`. Removing arbitrary drivers is **not** yet automatic:
update that source-derived dependency/load/alias patch from Google's original as well as the
selection and base includes. Recipes organize the current combined image, not independent
selectable-laptop builds or a runtime driver installer.

For another driver, first check whether Ruby already ships a suitable module. Otherwise,
add only the required native fragments, select the recipe and place its includes in the
appropriate base lists. `make hardware-check` checks this wiring without building the image.
A recipe declaration is not hardware verification; see the [hardware spec](../docs/specs/laptop-hardware.md).

Device- and driver-specific tests live in each recipe's `tests/` directory, beside the code
they verify. Shared tool/safety and cross-recipe integration tests stay in [tests/](../tests/).
`make test` runs both generic tests and every recipe's tests, including unselected recipes;
it does not build an image. For a focused run, pass files or directories:

```sh
scripts/builder.sh python3 tools/run_tests.py hardware/lenovo-e50-80/tests tests/test_overlay.py
```

Tests use local fixtures, never physical devices. Shared fixture helpers live in
[recipe_support.py](../tests/recipe_support.py); recipe tests need no package boilerplate or
per-recipe runner.

### Laptop test image

```sh
make android-image       # creates/updates out/gbos-builder/ruby-16693588/compact/disk.img
make android-uefi-check  # disposable USB/UEFI boots in QEMU; no physical writes
```

Use a **64 GB or larger USB**, preferably USB 3. Install
[out/gbos-builder/ruby-16693588/compact/disk.img](../out/gbos-builder/ruby-16693588/compact/disk.img)
with `make install-usb`: **fresh installation erases that USB**.
The 12 GiB super partition contains system 3 GiB, vendor 1.5 GiB, product 4 GiB,
system_ext 1.5 GiB and both module partitions 256 MiB: 10.5 GiB allocated, about 1.5 GiB spare.
See [super-layout.json](../android/super-layout.json). The 14-entry compact GPT removes unused
ChromeOS/B/C boot entries; only `vbmeta_b` remains for Google's boot-control HAL.
Metadata and small security/persistent partitions remain separate.
The 576 MiB EFI-SYSTEM holds boot files; trailing userdata defaults to 32 GiB for QEMU
and fills the USB during fresh installation. Raw imaging tools do not perform that expansion
or reset copied Android encryption/data state; use the supported installer.
Older local disk images remain in place. The current disk path includes the Ruby build number;
the previous compact image may have a different EFI-SYSTEM UUID and is not a bootable fallback.
**A USB with a different GPT identity needs a full reflash**, erasing its accounts and data; the
updater deliberately refuses mismatched GPTs. Afterwards, **update instead of reflashing** to
preserve Android data while the GPT identity remains the same. Normal boots omit the firmware
framebuffer, following owner-confirmed tests on both laptops; a saved previous menu may predate
the EFI crash-logging safeguard. The debug entry shows the earliest kernel messages for a black
screen but adds about a minute to the boot.

#### Compact partition layout

This is a GPT disk image, not an ISO. The layout below is implemented and covered by focused
regular-file tests; the compact image build and boot checks are still pending.
Physical partitions appear in this order, with 1 MiB-aligned starts:

| GPT partition | Size | Purpose |
|---|---|---|
| `EFI-SYSTEM` | 576 MiB | FAT32 `GBOS-BOOT`: GRUB, kernel, initrd and saved translator choice |
| `super` | 12 GiB | Container for the six logical Android OS partitions below |
| `boot_a` | 64 MiB | Retained Android boot/AVB partition |
| `init_boot_a` | 8 MiB | Retained Android init-boot/AVB partition |
| `vendor_boot_a` | 32 MiB | Retained Android vendor-boot/AVB partition |
| `vbmeta_a` | 4 MiB | Active slot-A AVB metadata and GPT boot-control attributes |
| `vbmeta_b` | 4 MiB | Compatibility entry for Google's boot-control HAL, not a second OS |
| `misc` | 4 MiB | Android boot/recovery control messages |
| `metadata` | 64 MiB | Android encryption metadata |
| `desktop_security_persist` | 16 MiB | Retained Google security/persistent storage |
| `desktop_security_storage` | 32 MiB | Retained Google security storage |
| `frp_persist` | 2 MiB | Retained factory-reset-protection storage |
| `gbos_logs` | 256 MiB | FAT32 `GBOS-LOGS`: direct, opt-in diagnostic captures |
| `userdata` | Initially 32 GiB | Android apps, accounts and files; expanded during fresh USB installation |

Small security partitions are retained conservatively; their removal has not been proven safe.
Sizes other than EFI, super and userdata follow the pinned Google recovery.
Retained partition UUIDs/types are preserved, including the ESP UUID used to locate the disk.

Inside `super`, [super-layout.json](../android/super-layout.json) declares:

| Logical partition | Allocation |
|---|---|
| `system_a` | 3 GiB |
| `vendor_a` | 1.5 GiB |
| `product_a` | 4 GiB |
| `system_ext_a` | 1.5 GiB |
| `system_dlkm_a` | 256 MiB |
| `vendor_dlkm_a` | 256 MiB |
| **Total** | **10.5 GiB**, leaving about **1.5 GiB** for future allocation changes |

Logical allocations include room for filesystem growth. Spare super space is not automatically
added to a full logical partition: changing an allocation changes the layout and requires a
fresh installation under the current updater contract.

`ANDROID_DATA_GIB` controls the initial sparse userdata size for QEMU. After copying and
verifying a fresh USB installation, the installer resets copied Android encryption/data state,
moves the backup GPT to the device's end and extends userdata into the remaining usable space.
Android formats it on first boot. Ordinary updates preserve userdata and metadata, allow a
larger target userdata partition, and never repartition; older layouts require a fresh install.

**Direct FAT32 diagnostics pass focused tests; image/boot validation is pending.** The diagnostic GRUB
entry mounts `GBOS-LOGS` at `/metadata/gbos-builder-bootlog` and writes there directly;
the path is a mountpoint, not storage on metadata. There is no export/copy loop.
Only current/previous diagnostic boots are retained with the existing stream limits.
Normal boots leave the log partition unmounted, and updates preserve it unchanged.
Mount failure is reported and prevents persistent collectors from starting; Android continues.
The guest never auto-formats or repairs this partition and never falls back to metadata.
Synchronous FAT writes favor recoverable diagnostics over diagnostic-boot performance;
a power loss can still damage FAT or lose evidence. Logs are unencrypted and readable by
anyone with the USB: keep them private.

At the GRUB menu, use the arrow keys to highlight **Googlebook OS (Berberis)** or
**Googlebook OS (Houdini)**, then press Enter. The highlighted translator is the saved default:
GRUB starts it automatically after the menu timeout, and choosing the other translator changes
the default for future boots too. This is a persistent choice, not a one-boot override. A fresh
or missing saved choice defaults to Berberis. The setting is kept in the ESP-root `grubenv`,
outside the two directories replaced by updates, so updating boot files preserves it.

The diagnostic and debug menu entries do not change the saved translator choice; those
entries use Berberis for that boot. A failed Berberis or Houdini boot also does not switch choices
automatically. Return to GRUB and choose the other translator to change the saved default.

Berberis (`libndk_translation.so`) is the default ARM-to-x86 translator. The owner confirms the
previously failing game, another native app and Hearthstone work on the laptop with Berberis.
In enforcing QEMU on this host, a small ARM64 executable traps in Houdini but runs with Berberis;
Houdini's exact failure cause remains unknown. Disposable UEFI/QEMU checks confirm both saved
choices reach Android and persist in `grubenv`; physical menu selection has not been tested.
The boot record names the selected translator, and a separate `crash.log*` retains fatal records
independently of noisy desktop logs.

Disable Secure Boot and choose the USB's UEFI entry. GRUB selects AMD graphics on the MSI's
`1002:15e7` GPU and Intel graphics on the Lenovo's Broadwell `8086:1616`.
The Intel profile uses Iris GLES and hasvk Vulkan; the owner confirms Chrome and camera work
after the hasvk Android-buffer query fix. Both laptops use panel density 160; QEMU keeps 240
and softpipe. The internal NVMe remains hidden on the laptop.
Signed amdgpu modules, official runtime firmware, RADV/Zink, ANGLE and AMD-capable minigbm
are included. The owner has confirmed the built-in microphone, camera preview and video recording.
HDMI display performance feels fine, though its frame rate has not been measured. The brightness
slider, MSI Bluetooth pairing, headphone output and suspend remain unverified; HDMI audio is
not implemented. Lenovo Bluetooth, audio and microphone are owner-confirmed.
Details and evidence: [laptop hardware](../docs/specs/laptop-hardware.md).
Normal boots do not run the project's persistent log collectors or hardware snapshot.
To investigate a problem, reboot using **Googlebook OS (diagnostic logs)** and reproduce it.
Persistent kernel/Android diagnostics use native logcat and retain current/previous diagnostic
boots on the dedicated FAT32 log partition,
with an explicitly approved scoped enforcing policy. See [boot](../docs/specs/boot.md) for limits/coverage
and [laptop hardware](../docs/specs/laptop-hardware.md#recovering-the-new-boot-logs)
for Linux retrieval.

### Updating the existing Android USB

Stop any VM using the image, plug in the Android USB and unmount its partitions (including
**GBOS-BOOT**) in the file manager. Then run as your normal user:

This requires a USB already flashed with the expanded A-only layout above. It cannot upgrade
the older layout in place.

```sh
make update-usb
```

This builds changed components, then asks for sudo to run the tracked
[USB updater](../tools/update_usb.py) on the host. Choose a numbered USB disk from its model,
capacity and serial; review the planned OS and boot-file changes, then type `y` or `yes`
at the `[y/N]` prompt to confirm. Enter or any other answer cancels without writing.

The updater:
- Accepts only an **existing gbos-builder Android USB**, not a blank disk or another OS.
- Refuses internal disks, missing serials, mounted/in-use disks and incompatible GPT/liblp layouts.
- Derives OS ranges from the built image, copies only changed partitions and verifies read-back.
- Updates kernel, initrd and GRUB together using the existing menu-last boot installer.
- Preserves `/data`, metadata and partition tables, including an already enlarged userdata.
- Unmounts its private boot mounts but leaves the USB attached to Linux; no replug is needed.

If interrupted, rerun it before booting Android. It is an updater, not an installer: it never
formats or repartitions. It replaces the ignored, machine-specific `update-os.sh`.
Host requirements are Python 3, sudo and util-linux (`lsblk`, `sfdisk`, `mount`, `umount`).
Builds still run inside the Debian builder; only explicit physical-device deployment runs on the host.
Keep downloads, sources and build directories in `out/`; deleting them makes the next build slow.

### Fresh USB installation (erases the USB)

Unmount every partition of the USB, stop any VM using the source image, then run:

```sh
make install-usb
```

This builds the Android image, then runs the host [fresh flasher](../tools/install_usb.py).
Select a USB by model, capacity and serial before sudo authentication. Review the erase warning
and confirm with `y` or `yes` at `[y/N]`. Enter or any other answer cancels without writing.
Internal disks, missing serials, mounted/in-use, read-only and undersized devices are refused.
The whole image is copied and SHA-256 read-back verified; **all existing USB data is lost**.
After read-back, the installer clears metadata and the userdata filesystem signature,
relocates the backup GPT to the USB's end and expands only the trailing userdata partition.
Android formats fresh encrypted data at the expanded size on first boot. This also discards
any accounts/data copied from a QEMU-used image; it is not a secure erase of all old sectors.
The final GPT is checked against the source, allowing only larger userdata, and verified.
Ordinary `make update-usb` never performs this initialization, growth or GPT relocation.
Safely unplug/replug afterwards, then boot its UEFI entry.
If interrupted or verification fails, rerun installation before booting; do not trust a partial USB.
The agent tests this tool on regular files only; physical installation is your operation.

### Reading laptop logs

After returning to Linux, connect the Android USB and unmount its partitions, then run:

```sh
make laptop-logs
```

Select the USB by model/serial. Sudo authorizes read-only mtools (`mdir`/`mtype`); no mounts,
filesystem repair or USB writes occur. Current and previous boot logs are copied to a private,
timestamped folder under `out/laptop-logs/`, owned by your normal user.
`out/laptop-logs/latest/current/` always points to the newest successful retrieval; older copies
are retained.

No sudo or terminal? Shut Android down, connect the USB to a desktop computer and open the
`GBOS-LOGS` FAT32 volume in its file manager. Copy `current/` and `previous/` to a local folder.
Only open this named volume; cancel any request to format other partitions and do not change
their contents. The volume uses a standard FAT32 filesystem, but file-manager browsing has not
been tested on Windows or macOS.

Only the diagnostic entry saves new logs; normal boots leave earlier captures untouched.
Check the saved boot identity/time rather than assuming it describes the latest normal boot.
Retrieval needs host mtools, sudo, lsblk and Python 3; it does not build an image.
Older images without `gbos_logs` still use read-only `debugfs` (e2fsprogs) on metadata.
The direct-FAT32 path passes regular-file tests; physical capture/retrieval is unverified.
Treat the logs as private.

Optional, once: more space in `/data`. Android cannot enlarge its encrypted ext4 in place, so
the owner's local [grow-data.sh](../out/usb-flash-android/grow-data.sh) enlarges the `userdata`
partition into the free space behind it and blanks its first MiB; Android then formats `/data`
at the new size on the next boot. **That erases Android's accounts, apps and files** and setup
runs again, so it needs `--erase-data` and a typed `ERASE` (a blank partition grows without
them). Run it right after a flash and nothing of yours is lost. It never shrinks the partition
and refuses any other layout. This helper remains specific to the owner's Seagate stick:

```sh
sudo -- bash out/usb-flash-android/grow-data.sh --erase-data 128   # GiB; omit the size for all free space
```

Later `make update-usb` runs accept the larger partition; reflashing returns to `ANDROID_DATA_GIB`.

An unchanged image build writes no partitions or boot files. A successful QEMU check is a useful
regression test, not proof of working laptop audio, brightness or GPU acceleration.

## Where to read the code

| File | Responsibility |
|---|---|
| [Makefile](../Makefile) | Dependencies and commands; `make` shows everyday commands, `make help-all` every target |
| [tools/update_usb.py](../tools/update_usb.py) | Select and update an existing Android USB; preserve data and verify writes |
| [config.mk](../config.mk) | Output path, jobs, recovery path, USB mountpoint, QEMU sizes |
| [sources.mk](../sources.mk) | Source URLs, exact revisions and SHA-256 pins |
| [docker/Dockerfile](../docker/Dockerfile) | Debian build/test tools |
| [scripts/fetch.sh](../scripts/fetch.sh), [scripts/source.sh](../scripts/source.sh) | Verified download and source extraction |
| [scripts/kernel-source.sh](../scripts/kernel-source.sh) | Checked kernel checkout with the emulator patch and our [kernel/](../kernel/) source patches (`KERNEL_PATCHES` in the Makefile) |
| [boot/loader.cfg](../boot/loader.cfg) | GRUB's built-in loader: finds this USB's menu |
| [tools/deploy.py](../tools/deploy.py), [tests/test_deploy.py](../tests/test_deploy.py) | Android boot-bundle verification and menu-last boot-file installs |
| [scripts/git-fetch.sh](../scripts/git-fetch.sh), [scripts/pahole.sh](../scripts/pahole.sh) | Google's pinned kernel compilers, verified against Git |
| [scripts/gki-kernel.sh](../scripts/gki-kernel.sh), [kernel/gki.config](../kernel/gki.config) | Google's kernel plus explicitly listed configuration changes, with config/ABI checks |
| [scripts/laptop-modules.sh](../scripts/laptop-modules.sh), [scripts/firmware.sh](../scripts/firmware.sh) | Missing signed AMD modules and unchanged official firmware |
| [android/cmdline.txt](../android/cmdline.txt), [android/bootconfig.txt](../android/bootconfig.txt) | Settings Android boots with: Google's + our listed changes |
| [scripts/android-initrd.sh](../scripts/android-initrd.sh), [tools/android_disk.py](../tools/android_disk.py) | Android's module-extended initrd and compact private GPT disk |
| [boot/android-menu.cfg](../boot/android-menu.cfg), [scripts/android-boot.sh](../scripts/android-boot.sh) | The laptop's GRUB menu for Android, and writing its boot files into the disk's FAT32 partition |
| [scripts/qemu.sh](../scripts/qemu.sh) | The QEMU virtual machine Android runs in |
| [scripts/mesa.sh](../scripts/mesa.sh) | Android Mesa, libdrm and Expat from source with the NDK |
| [scripts/minigbm.sh](../scripts/minigbm.sh), [tools/minigbm_abi.py](../tools/minigbm_abi.py) | AMD-capable allocator build, checked against Google's existing clients |
| [android/system/](../android/system/), [android/system_ext/](../android/system_ext/), [android/vendor/](../android/vendor/), [android/module_ramdisk/](../android/module_ramdisk/) | Every change to Google's files: `remove.list`, `install.list` and `*.patch` per target |
| [scripts/android-overlay.sh](../scripts/android-overlay.sh) | Applies one change directory: removes, installs with owner/mode/label, patches in place |
| [scripts/check-vendor-libs.sh](../scripts/check-vendor-libs.sh) | Refuses vendor programs we install that link to libraries Android would not find |
| [scripts/check-replacements.sh](../scripts/check-replacements.sh) | Refuses replacements of Google's files that are not drop-in: missing imported exports, or an APEX with another name, version or file list |
| [scripts/android-partition.sh](../scripts/android-partition.sh), [tools/fs_metadata.py](../tools/fs_metadata.py) | Rootless EROFS rebuilding and complete content/metadata comparison |
| [tools/android_sync.py](../tools/android_sync.py) | Named OS partition updates, preserving Android's data |
| [tools/android_smoke.py](../tools/android_smoke.py), [tools/android_console.py](../tools/android_console.py) | Full-boot checks and framed serial-shell commands |
| [tools/android_uefi_test.py](../tools/android_uefi_test.py) | Laptop boot-chain checks on disposable USB images, with an NVMe decoy |

`make sources` creates editable trees under `out/src/`. `make gki` always runs Kbuild so
edits there are detected, not hidden by a top-level "done" stamp. Published outputs retain their
timestamps if their bytes are unchanged. The source trees and outputs are ignored by Git:
**save source edits before deleting `out/` or changing pins or patches**. A new kernel patch creates
another checkout without copying edits from the old one. There is intentionally no blanket
`make clean` deleting your source experiments.

The compiler and other host tools come from Debian packages; they are not bit-for-bit pinned.
The **target kernel** is compiled here with Google's pinned compilers. The EFI loader is
Debian's GRUB package, used unchanged.
Changing the compiler or a source pin warrants a fresh build output directory (`OUT=out/new`).

## Google's image

```sh
make unpack
less out/google/inventory.txt
```

[scripts/unpack.sh](../scripts/unpack.sh) verifies the image's pinned SHA-256 before extracting boot
images, logical partitions, properties and kernel identity. The default image and its hash are in
[config.mk](../config.mk); when using another recovery image, set both `RECOVERY_IMAGE` and
`RECOVERY_IMAGE_SHA256`. This inspection step does not build or deploy Android. Recovery models are listed at
<https://aluminium-os.com/googlebookos/>.

The inspected Lenovo Googlebook 15 (`ruby`) image contains Android 17 and kernel
`6.18.21-android17-5-g3938c8d97142-ab16302624`. Google's vendor modules need the GKI build
below, from that kernel's source with Google's compilers.

## Googlebook OS kernel (GKI)

```sh
make toolchain           # Google's pinned clang, Rust and bindgen (about 7 GB) + pahole from source
make gki                 # about an hour the first time; incremental afterwards
```

This rebuilds Google's own kernel from source so that Google's unmodified modules still load.
The compilers are the exact versions named in Google's build manifest. They come from
googlesource.com archives of the pinned commits, and [scripts/git-fetch.sh](../scripts/git-fetch.sh)
uses Git to prove the files match those commits. pahole is compiled from Google's pinned dwarves
source.

[scripts/gki-kernel.sh](../scripts/gki-kernel.sh) starts from Google's `config`, applies the
changes in [kernel/gki.config](../kernel/gki.config) and selected driver recipe configs, and refuses
to build if:

- a requested change did not take effect;
- any other built-in option differs from Google's;
- a compiler version differs from Google's ([tools/kconfig_check.py](../tools/kconfig_check.py)).

Like Google's build, it keeps only the exports listed in Google's published
`abi_symbollist.raw` plus those Google's own modules use. After building, it refuses to publish a
kernel whose release string differs from Google's, or that is missing any of Google's exported
symbols or exports one with a different checksum ([tools/kabi_check.py](../tools/kabi_check.py)).
Google's signing certificate is extracted from Google's kernel
([tools/kernel_certs.py](../tools/kernel_certs.py)) and trusted, so Google's signed modules load.
QEMU's virtio GPU, input and network drivers are not compiled here: they are Google's prebuilt
modules for this same kernel, from its virtual-device build (`GKI_VIRT` in
[sources.mk](../sources.mk)). Output: `out/gki/bzImage`.

## CPU-portable BoringSSL

```sh
make boringssl
```

This builds upstream `libcrypto.so` and `libssl.so` into `out/boringssl/`; the standalone target
does not update the image. `make android-image` installs the pair into system/vendor.
Every build uses these portable libraries; upstream dispatches internally for the running CPU.
There is no boot-time stock/portable selector.
Google's crypto uses SHA-NI instructions that Broadwell must emulate.
The pinned emulator libraries cannot replace it: they lack required exports.

The source pin and official host Go tool are in [sources.mk](../sources.mk).
[boringssl.sh](../scripts/boringssl.sh) builds unchanged upstream with `-march=x86-64-v3`,
runtime CPU detection and upstream's FIPS integrity machinery (not a certification claim).
It links Google's platform libc++, like minigbm, rather than adding a custom C++ shim.
[crypto_abi.py](../tools/crypto_abi.py) requires all original system/vendor/Conscrypt exports with matching
types, bindings, visibility and data-object sizes before publishing either library.
This does not prove opaque structure layouts or runtime compatibility.

[crypto.rc](../android/system/crypto.rc) bind-mounts the system pair over Conscrypt's copies
after APEX activation and before zygote starts. The signed APEX stays unchanged. Its
[policy patch](../android/system/crypto-policy.patch) adds only init file-mount permission on
`system_lib_file`; this is type-scoped, not restricted to specific target paths.

Verified in enforcing QEMU: setup screen, mounts inherited by zygote/system_server, upstream
integrity/crypto self-tests, 10,000 SHA-256 known-answer checks, TLS context creation and
certificate-verified HTTPS against a temporary local server through system and Conscrypt paths.
The local server avoids QEMU's unfinished DNS/default-route setup. Repeat image builds preserve
published timestamps and write no partitions.
The owner confirms faster Chrome launches and page loads on Lenovo. Its new logs show
284,898 SHA-256 traps over about 160 seconds versus 49,743,288 over about 605 seconds before;
these are different sessions, not a controlled benchmark. The Conscrypt trap storm is absent.
Not verified: measured CPU utilization or MSI regression with these libraries.

### HttpEngine crypto

`make httpengine-crypto` builds the separate `libcrypto_httpengine.so` into
`out/httpengine-crypto/`; `make android-image` installs it and overlays Tethering's copy.
HttpEngine/Cronet 150.0.7871.41 pins a different BoringSSL revision in
[Chromium DEPS](https://chromium.googlesource.com/chromium/src/+/150.0.7871.41/DEPS).
[httpengine-crypto.sh](../scripts/httpengine-crypto.sh) checks the engine version and requires
exactly the original 323 versioned exports, including Chromium's `std::__Cr` helpers.
It builds unchanged upstream, non-FIPS, with runtime CPU dispatch. The
[header](../scripts/httpengine-cxx.h) uses libc++'s supported fatal-abort hook instead of a
hand-written Chromium C++ shim. Signed Tethering bytes and SELinux permissions are unchanged.
Wi-Fi and other APEX crypto copies are not replaced.

Verified: 29 focused tests, image metadata/fit, enforcing QEMU setup screen and inherited
mount hashes; the real HttpEngine native library loads with immediate symbol resolution.
10,000 SHA-256 known answers and Chromium reference-count cycles pass. An unchanged image
repeat preserves published timestamps and writes no partitions or boot files.
The Java request probe failed during standalone ART startup, before calling HttpEngine;
successful HttpEngine HTTP/TLS requests and physical trap reduction remain unverified.
Evidence: [HttpEngine investigation](../out/httpengine-investigation/).

Subsequent Lenovo test: owner accepts the image for continued use; video plays but raises CPU.
[Saved logs](../out/laptop-logs/20261104-193204-2vm8v68i/current/) contain no HttpEngine trap
samples. Highest logged counters over about 351 seconds are 190,311 SHA-256, 148,506 GFNI
and 5,654 VNNI; these are rate-limited counters, not exact totals or CPU measurements.
The last sampled SHA trap is in Bluetooth's separate crypto copy. Intel VA initializes and
advertises H.264/VP8 decoders, but playback's selected codec/decoder is not retained.
No dedicated successful HttpEngine HTTP/TLS request or MSI regression test is established.

## Googlebook OS in QEMU

```sh
make qemu                # builds what changed, then boots; use a VNC viewer on localhost:5900
less out/qemu/kernel.log # kernel and Android init log of the last run
```

Google's image is the read-only starting point. Only `system`, `system_ext`, `vendor` and
`vendor_dlkm` are rebuilt, with the changes listed below. QEMU uses this laptop's CPU
(`-cpu host`, KVM); its only disk is
`out/gbos-builder/ruby-16693588/compact/disk.img`. The serial shell and QMP monitor are local
Unix sockets under `out/qemu/`. Use Android's shutdown menu for an orderly shutdown; Ctrl-C stops QEMU.
Virtual ACPI S3/S4 sleep is disabled for reliable development sessions. Input uses a standard
virtio keyboard and relative mouse; the tablet's absolute pointer protocol is not used.

- **Kernel:** `out/gki/bzImage` from `make gki`.
- **Command line:** [android/cmdline.txt](../android/cmdline.txt), Google's with the listed changes.
- **Initrd** (`make android-initrd`): Google's boot ramdisks plus Google's prebuilt
  virtio-gpu, input and network modules, then the boot settings: Google's
  plus [android/bootconfig.txt](../android/bootconfig.txt), packed by
  [tools/bootconfig.py](../tools/bootconfig.py).
- **Disk** (`make android-disk`): the versioned `out/gbos-builder/ruby-16693588/compact/disk.img`,
  a fresh compact GPT
  built by [tools/android_disk.py](../tools/android_disk.py), with A-only super assembled by
  [tools/android_fresh.py](../tools/android_fresh.py) using upstream lpmake.
  Retained partition UUIDs and contents are preserved, except new boot storage, blank metadata
  and sparse userdata of `ANDROID_DATA_GIB`. Slot A is marked bootable/successful.
  The disk holds Android's data after boot, so it is never recreated automatically.
- **Boot files** (`make android-boot`): GRUB, the GKI kernel, the initrd and the menu
  [boot/android-menu.cfg](../boot/android-menu.cfg) are written into that FAT32 partition with
  mtools, without root or a mount. QEMU's direct-kernel boot does not read them; the laptop's
  firmware will. The menu is Google's command line plus laptop-only arguments, including one that
  hides the internal NVMe. The script refuses any partition not labelled `GBOS-BOOT`, replaces the
  `EFI/` and `gbos-builder/` trees as a whole and writes nothing when they already match.
- **Update** (`make android-image`): rebuild changed inputs, copy only changed OS
  partitions into that disk with checksum read-back, and refresh the boot files. `userdata`,
  `metadata` and the partition layout remain unchanged. Stop the VM first: a shared lock
  prevents updates while it runs. An interrupted update is repaired by rerunning the command,
  not by deleting Android's data.

### Checking the laptop boot chain

`make android-uefi-check` boots disposable copies through OVMF and GRUB, as USB storage
beside a writable NVMe decoy. It checks that Android finds the USB partitions, never enumerates
the decoy and leaves its bytes unchanged. No physical drives are accessed.

There are two display configurations: `virtio-vga` for the serial-shell USB boot check,
then `virtio-gpu-pci` for Android's setup UI. Both reject a firmware framebuffer; neither
proves a laptop boot. Both use the installed laptop menu with only
a serial-console argument added to the copy. Logs and screenshots go in fresh
`out/android-uefi-*` directories; inspect the screenshots, not just the printed PASS.
See [laptop hardware](../docs/specs/laptop-hardware.md) for verified results and limitations.

### Explicit VM changes

Every change to Google's files is declared in one directory per target, applied by
[scripts/android-overlay.sh](../scripts/android-overlay.sh) in this order:

| File | Meaning |
|---|---|
| `remove.list` | Paths to delete; each must exist |
| `install.list` | New files: path, mode, owner, SELinux type, source (this directory or a named build input) |
| `*.patch` | Unified diffs of Google's text files, with a header saying why |

The targets are [android/system/](../android/system/), [android/system_ext/](../android/system_ext/),
[android/vendor/](../android/vendor/), [android/vendor_dlkm/](../android/vendor_dlkm/) and the first-stage module ramdisk
[android/module_ramdisk/](../android/module_ramdisk/). Patched files keep their owner, mode and
SELinux label. To change something, edit a list or a patch; regenerate a patch with
`diff -u --label a/PATH --label b/PATH google-file edited-file` against Google's original.

- Google's Trusty security VM cannot supply KeyMint here. Its service/VINTF declarations are
  removed; software KeyMint/Gatekeeper and their missing library dependencies come **unmodified**
  from the SHA-256-pinned Android 17 emulator. Software keys are **not hardware protected**.
  Remote attestation provisioning is disabled; this is not a certified or Play-Integrity device.
- Mesa EGL/GLES, softpipe, Zink and RADV are built from source, with libdrm/Expat linked statically.
  Google's DRM composer, mapper and allocator service remain; minigbm's libraries are rebuilt
  with AMD support and an ABI check against those clients. Virtio-gpu supplies QEMU scanout.
  [mesa-drm-master.patch](../hardware/drivers/drm-handoff/mesa-drm-master.patch) fixes Mesa's Android software
  renderer retaining DRM master after opening a primary node, which otherwise prevents the
  composer from displaying anything. This is a small **source patch**, not a binary edit or
  added service privilege. [android/vendor/build-prop.patch](../android/vendor/build-prop.patch)
  contains common graphics settings; selected [hardware recipes](../hardware/) install the
  AMD, Intel and softpipe graphics profiles.
- Google builds bionic (libc, linker and the runtime APEX) and libz for Intel Panther Lake. On
  older CPUs their GFNI/AVX-VNNI instructions trap into the kernel's emulator thousands of times
  a second. The same files from the pinned Android 17 emulator image, a generic x86-64 build,
  replace them **unmodified**; [scripts/check-replacements.sh](../scripts/check-replacements.sh)
  checks each is a drop-in. Remaining traps are rare (Rust std, HWUI, ART).
- Google's power HAL configuration pins cpusets to Panther Lake's 8 CPUs; on the laptop's 12 it
  kept apps off 4 CPUs and background work on 4. [powerhint.patch](../android/vendor/powerhint.patch)
  removes only those masks, so Android's default all-CPU cpusets stay.
- Google's memory daemon (mmd) makes an 8 GiB writeback file in `/data` on every boot and writes
  idle zram pages out to the USB. [android/vendor/build-prop.patch](../android/vendor/build-prop.patch)
  turns writeback off, so swap stays in RAM and that space stays free.
- Google firmware updaters (including the security-chip update that blocked startup for 10 s
  waiting for a TPM), OTA and the absent EC logger are removed. The only replacement
  firmware command is [android/crossystem-qemu.c](../android/crossystem-qemu.c), compiled from source:
  it accepts the boot HAL's success assignments for this VM, rejects everything else, and never
  accesses firmware.
- EROFS extraction/rebuilding runs under fakeroot. After rebuilding, **every file's contents,
  mode, uid/gid and xattrs (including SELinux labels) are compared** with the intended tree.
  No mount or privileged container is used. SELinux stays enforcing.
- AVB verification is explicitly disabled for these development partitions using `avbtool`
  to generate a new vbmeta image. No byte-offset edits to vbmeta or executable code.

`make qemu-check` waits for `sys.boot_completed=1` **and the boot animation to exit**, then requires
stable system_server, SurfaceFlinger, KeyMint and Gatekeeper PIDs for 30 seconds, SELinux enforcing,
a reported softpipe renderer and 1280x720 QEMU scanout. It saves `out/qemu/screen.png`,
`boot-state.txt`, `surfaceflinger.txt`, `kernel.log` and `logcat.txt`. A serial shell or a boot logo
alone is not a passing result. The captured screen also needs visual inspection.

Verified locally: the actual Googlebook welcome/setup screen at 1280x720, with Mesa softpipe,
software keys and SELinux enforcing, VNC connection, mouse navigation into the language picker,
and clean guest shutdown. The `make test` unit tests pass; unchanged builds preserve output
timestamps and write no OS partitions, and a running VM rejects disk updates. A repeat boot completes
in about 20 seconds, because the softpipe profile skips the boot animation and shader priming; allow
several minutes for the first CPU-rendered startup on fresh data. Setup completion, Google account sign-in, hardware-backed attestation
and laptop performance are **not** claimed as tested. Bluetooth, Wi-Fi and audio hardware are
not presented to this VM; QEMU provides a virtual Ethernet adapter instead.

For iterations, stop the VM, edit the relevant source/configuration, and rerun `make qemu`.
Mesa source/toolchain/patch changes get separate build caches; ordinary source edits rebuild
incrementally. Downloads are kept by SHA-256 and never refetched; Meson configures again only when
its settings change. Only affected EROFS filesystems are rebuilt, and only changed OS partitions
are copied into the existing disk. An unchanged build writes no disk partitions.

## Hardware status

Device-by-device status, evidence and next steps for the laptop are in
[laptop hardware](../docs/specs/laptop-hardware.md); the overall order of work is in the
[project plan](../docs/plan.md).

**Known emulator limitation:** the imported patch handles VEX GFNI, not legacy SSE-encoded
GFNI (an early boot test confirmed that the latter raises SIGILL). Android boots on the MSI
exercise the VEX paths constantly, but that is not proof of every instruction/encoding.
Keep that distinction when evaluating new userspace binaries.

## Source attribution

- Kernel: [Android common](https://android.googlesource.com/kernel/common/), tag
  `android17-6.18-2026-06_r52`, GPL-2.0.
- GRUB: [2.12](https://www.gnu.org/software/grub/), GPL-3.0-or-later; Debian's
  `grub-efi-amd64-bin` package.
- Graphics: [Mesa](https://mesa3d.org/), [libdrm](https://dri.freedesktop.org/libdrm/) and
  [Expat](https://libexpat.github.io/), built from the pinned upstream sources and their licences.
- Allocator: [LineageOS minigbm](https://github.com/LineageOS/android_external_minigbm-upstream),
  with the documented source patch; AMD runtime blobs from official
  [linux-firmware](https://gitlab.com/kernel-firmware/linux-firmware), unchanged.
- Development security HALs: unmodified binaries from Google's pinned Android 17 emulator
  image. Googlebook userspace remains proprietary recovery-image content, not a source rebuild
  or a claim of redistribution permission.
- Instruction-emulation source patch: [vex-emulate.patch](../hardware/drivers/cpu-vex/vex-emulate.patch),
  preserved unchanged from Project Churro commit `488dab956808916100eca141ee251a5a5773eeba`.
  Vendored, content-hashed and applied to kernel **source**, with the user's approval.
  The reference repository has no top-level licence; resolve redistribution permissions before
  publishing its patch or resulting images. The project's MIT license does not relicense this
  third-party patch.

The original local reference ports have been removed. Investigate fixes through authoritative
upstream sources and this project's logs and tests. None of this pipeline edits executable bytes.
