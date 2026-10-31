# gbos-dali

A small, readable build for developing a Googlebook OS port on the **MSI Modern 15 B7M**.
Google's recovery image is a read-only input, not something we patch with byte offsets.

**QEMU first:** plain Googlebook OS with a source-built GKI kernel and Mesa softpipe,
plus the approved software KeyMint/Gatekeeper from Google's emulator. No KernelSU, dual-boot
installer, host-GPU passthrough or physical-disk writes. The separate USB diagnostic target is
retained, but it does not run Android.

## Build and boot

For Googlebook OS, Linux needs Docker, GNU make, Python 3, `/dev/kvm` and a VNC viewer.
Allow at least 50 GB for sources, builds and recovery images, plus Android's sparse data partition.

```sh
make qemu JOBS=12         # build changed components and run; VNC viewer: localhost:5900
make console COMMAND='getprop sys.boot_completed'   # from another terminal
make qemu-check          # bounded graphical boot/stability check; shuts the VM down afterwards
```

`QEMU_VNC_PORT=5901` changes the localhost-only published port. Android has 4 virtual CPUs,
6 GB RAM and a 1280x720 software-rendered display by default. Softpipe is a correctness baseline,
**not accelerated graphics**; CPU instruction emulation is another performance cost. The next
performance step is accelerated Mesa, not KernelSU or an installer.

## Optional USB diagnostics (not Android)

Needs Linux, Docker, GNU make, Python 3 and about 15 GB free. Compilation runs as your user in
Debian, with four jobs by default (`JOBS=6` overrides it). The first run downloads source and
builder packages. There is no root container, host package installation or loop-device setup.

```sh
make builder
make usb                 # source -> kernel, initramfs, EFI loader -> out/dali-usb.img
make smoke               # boot a disposable copy through UEFI in QEMU
make test                # focused deployment and safety tests
```

Flash `out/dali-usb.img` with your preferred USB imaging tool, carefully selecting the USB.
**Flashing erases that USB.** `make usb` itself only creates a 514 MiB regular image file;
it never chooses or writes a physical disk. Disable Secure Boot and boot the USB's UEFI entry.
The shell uses the laptop screen and keyboard. An external USB keyboard is a fallback while
the laptop's input devices are being brought up.

The root filesystem is temporary RAM. `/boot` is this USB's FAT filesystem, selected by the
UUID passed from GRUB, not by scanning internal disks for a label. The kernel has internal
NVMe/SATA/MMC, SPI flash, TPM and EFI capsule writing disabled. No Google firmware updater or
installer is included. Logs are `/boot/logs/kernel.log`, `kernel.previous.log`, and `hardware.txt`.
Use `umount /boot && poweroff -f` to shut down cleanly before removing the USB.

## The fast development loop

Back in Linux, mount the USB's **DALI-BOOT** partition through your file manager. Then:

```sh
# Edit boot/init, then:
make deploy USB=/run/media/$USER/DALI-BOOT
```

This invokes the upstream incremental builds, but only changed outputs are published:

| Changed input | Rebuilt | Written to USB |
|---|---|---|
| `boot/init` | initramfs | new initramfs + boot menu |
| kernel source or `kernel/msi-diagnostic.config` | kernel via Kbuild | new kernel + boot menu |
| `boot/menu.cfg` | boot menu | boot menu only |
| nothing | nothing | **no files** |

Deployment refuses raw devices, non-mountpoints, internal disks, read-only/non-FAT filesystems,
symlinks and USBs without the Dali marker. It verifies bundle hashes, checks the actual destination
contents, writes and reads back new files, then changes the menu last. Logs, other user files and
other partitions are not touched. A failed transfer before that switch leaves the old menu.
The previous menu is available in GRUB.

Old content-addressed kernel/initramfs files are deliberately retained; they are not automatically
deleted. If space runs out, deployment fails explicitly. Remove obsolete `dali/kernel-<hash>` and
`dali/initramfs-<hash>` files only after checking that **neither** `dali/grub.cfg` **nor**
`dali/grub.previous.cfg` references them. Do not unplug during an update: FAT is not journalled,
and rename/fsync are not a guarantee against power loss or a USB controller lying about flushes.

`make image` / `make usb` assembles a fresh image when its bundle changes. For rapid iterations
use `make deploy`, **not** another whole-stick flash.

## Where to read the code

| File | Responsibility |
|---|---|
| [Makefile](Makefile) | Dependencies and commands; `make` lists targets |
| [config.mk](config.mk) | Output path, jobs, recovery path, USB mountpoint, QEMU sizes |
| [sources.mk](sources.mk) | Source URLs, exact revisions and SHA-256 pins |
| [docker/Dockerfile](docker/Dockerfile) | Debian build/test tools |
| [scripts/fetch.sh](scripts/fetch.sh), [scripts/source.sh](scripts/source.sh) | Verified download and source extraction |
| [scripts/kernel-source.sh](scripts/kernel-source.sh) | Exact Git commit checkout + verified emulator source patch |
| [scripts/kernel.sh](scripts/kernel.sh) | Kbuild plus the diagnostic hardware config |
| [kernel/msi-diagnostic.config](kernel/msi-diagnostic.config) | Explicit additions/removals from x86_64_defconfig |
| [scripts/busybox.sh](scripts/busybox.sh), [scripts/grub.sh](scripts/grub.sh) | Static shell utilities and UEFI loader builds |
| [boot/init](boot/init) | The complete runtime startup sequence |
| [boot/menu.cfg](boot/menu.cfg), [boot/loader.cfg](boot/loader.cfg) | Readable GRUB configurations |
| [scripts/initramfs.sh](scripts/initramfs.sh), [scripts/image.sh](scripts/image.sh) | Standard cpio/FAT/GPT assembly |
| [tools/deploy.py](tools/deploy.py) | Bundle verification and file-level USB updates |
| [tools/boot_test.py](tools/boot_test.py), [tests/test_deploy.py](tests/test_deploy.py) | Boot and incremental-update checks |
| [scripts/git-fetch.sh](scripts/git-fetch.sh), [scripts/pahole.sh](scripts/pahole.sh) | Google's pinned kernel compilers, verified against Git |
| [scripts/gki-kernel.sh](scripts/gki-kernel.sh), [kernel/gki.config](kernel/gki.config) | Google's kernel config + our listed changes, with config/ABI checks |
| [android/cmdline.txt](android/cmdline.txt), [android/bootconfig.txt](android/bootconfig.txt) | Settings Android boots with: Google's + our listed changes |
| [scripts/android-initrd.sh](scripts/android-initrd.sh), [scripts/android-disk.sh](scripts/android-disk.sh) | Android's module-extended initrd and private persistent data disk |
| [scripts/qemu.sh](scripts/qemu.sh) | The QEMU virtual machine Android runs in |
| [scripts/mesa.sh](scripts/mesa.sh) | Android Mesa, libdrm and Expat from source with the NDK |
| [tools/android_overlay.py](tools/android_overlay.py), [android/](android/) | Explicit VM filesystem changes and readable runtime settings |
| [scripts/android-partition.sh](scripts/android-partition.sh), [tools/fs_metadata.py](tools/fs_metadata.py) | Rootless EROFS rebuilding and complete content/metadata comparison |
| [tools/android_sync.py](tools/android_sync.py) | Named OS partition updates, preserving Android's data |
| [tools/android_smoke.py](tools/android_smoke.py), [tools/android_console.py](tools/android_console.py) | Full-boot checks and framed serial-shell commands |

`make sources` creates editable trees under `out/src/`. `make kernel` always runs Kbuild so
edits there are detected, not hidden by a top-level "done" stamp. Published outputs retain their
timestamps if their bytes are unchanged. The source trees and outputs are ignored by Git:
**save source edits before deleting `out/` or changing pins**. There is intentionally no blanket
`make clean` deleting your source experiments.

The compiler and other host tools come from Debian packages; they are not bit-for-bit pinned.
The **target kernel, BusyBox and EFI loader** are compiled here, not downloaded executables.
Changing the compiler or a source pin warrants a fresh build output directory (`OUT=out/new`).

## Google's image

```sh
make unpack
less out/google/inventory.txt
```

[scripts/unpack.sh](scripts/unpack.sh) extracts boot images, logical partitions, properties and
kernel identity. Set `RECOVERY_IMAGE` in [config.mk](config.mk), or on the command line. This
inspection step is independent of the diagnostic build: the USB **does not yet contain or start
Android**. Recovery models are listed at <https://aluminium-os.com/googlebookos/>.

The inspected Lenovo Googlebook 15 (`ruby`) image contains Android 17 and kernel
`6.18.21-android17-5-g3938c8d97142-ab16302624`. Our diagnostic build uses that kernel's source
commit, but a smaller upstream defconfig, GCC and its own release suffix. Google's vendor modules
need the GKI build below instead.

## Googlebook OS kernel (GKI)

```sh
make toolchain           # Google's pinned clang, Rust and bindgen (about 7 GB) + pahole from source
make gki JOBS=10         # about an hour the first time; incremental afterwards
```

This rebuilds Google's own kernel from source so that Google's unmodified modules still load.
The compilers are the exact versions named in Google's build manifest. They come from
googlesource.com archives of the pinned commits, and [scripts/git-fetch.sh](scripts/git-fetch.sh)
uses Git to prove the files match those commits. pahole is compiled from Google's pinned dwarves
source.

[scripts/gki-kernel.sh](scripts/gki-kernel.sh) starts from Google's `config`, applies the short
list of changes in [kernel/gki.config](kernel/gki.config), and refuses to build if:

- a requested change did not take effect;
- any other built-in option differs from Google's;
- a compiler version differs from Google's ([tools/kconfig_check.py](tools/kconfig_check.py)).

After building, it refuses to publish a kernel whose release string differs from Google's, or
that is missing any of Google's exported symbols or exports one with a different checksum
([tools/kabi_check.py](tools/kabi_check.py)). Google's signing certificate is extracted from
Google's kernel ([tools/kernel_certs.py](tools/kernel_certs.py)) and trusted, so Google's signed
modules and our newly built ones both load. Outputs: `out/gki/bzImage` and `out/gki/modules/`.

## Googlebook OS in QEMU

```sh
make qemu                # builds what changed, then boots; use a VNC viewer on localhost:5900
less out/qemu/kernel.log # kernel and Android init log of the last run
```

Google's image is the read-only starting point. Only `system`, `system_ext` and `vendor` are
rebuilt, with the changes listed below. QEMU uses this laptop's CPU (`-cpu host`, KVM);
its only disk is `out/android/disk.img`. The serial shell and QMP monitor are local Unix sockets
under `out/qemu/`. Use Android's shutdown menu for an orderly shutdown; Ctrl-C stops QEMU.
Virtual ACPI S3/S4 sleep is disabled for reliable development sessions. Input uses a standard
virtio keyboard and relative mouse; the tablet's absolute pointer protocol is not used.

- **Kernel:** `out/gki/bzImage` from `make gki`.
- **Command line:** [android/cmdline.txt](android/cmdline.txt), Google's with the listed changes.
- **Initrd** (`make android-initrd`): Google's boot ramdisks plus our matching
  virtio-gpu, input and network modules, then the boot settings: Google's
  plus [android/bootconfig.txt](android/bootconfig.txt), packed by
  [tools/bootconfig.py](tools/bootconfig.py).
- **Disk** (`make android-disk`): `out/android/disk.img`, a copy of Google's recovery image,
  instant and space-sharing on btrfs. [scripts/android-disk.sh](scripts/android-disk.sh) moves
  the 4 GiB data partition to the end and grows it to `ANDROID_DATA_GIB` (sparse), and marks
  slot A bootable. Its partition table is written next to it as `disk.img.layout.txt`. The disk
  holds Android's data, so it is never recreated automatically.
- **Update** (`make android-image`): rebuild changed inputs and copy only changed OS
  partitions into that disk, with checksum read-back. `userdata`, `metadata` and the partition
  layout remain unchanged. Stop the VM first: a shared lock prevents updates while it runs.
  An interrupted OS update is repaired by rerunning the command, not by deleting Android's data.

### Explicit VM changes

- Google's Trusty security VM cannot supply KeyMint here. Its service/VINTF declarations are
  removed; software KeyMint/Gatekeeper and their missing library dependencies come **unmodified**
  from the SHA-256-pinned Android 17 emulator. Software keys are **not hardware protected**.
  Remote attestation provisioning is disabled; this is not a certified or Play-Integrity device.
- Mesa EGL/GLES and softpipe are built from source, with libdrm/Expat linked statically.
  Google's DRM composer/minigbm remain; virtio-gpu supplies buffers and display scanout.
  [android/mesa-drm-master.patch](android/mesa-drm-master.patch) fixes Mesa's Android software
  renderer retaining DRM master after opening a primary node, which otherwise prevents the
  composer from displaying anything. This is a small **source patch**, not a binary edit or
  added service privilege. [android/vendor.props](android/vendor.props) contains the graphics settings.
- Google firmware updaters, OTA and the absent EC logger are removed. The only replacement
  firmware command is [android/crossystem-qemu.c](android/crossystem-qemu.c), compiled from source:
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
and clean guest shutdown. Seventeen focused tests pass; unchanged builds preserve output
timestamps and write no OS partitions, and a running VM rejects disk updates. Allow several minutes
for CPU-rendered startup. Setup completion, Google account sign-in, hardware-backed attestation
and laptop performance are **not** claimed as tested. Bluetooth, Wi-Fi and audio hardware are
not presented to this VM; QEMU provides a virtual Ethernet adapter instead.

For iterations, stop the VM, edit the relevant source/configuration, and rerun `make qemu`.
Mesa source/toolchain/patch changes get separate build caches; ordinary source edits rebuild
incrementally. Only affected EROFS filesystems are rebuilt, and only changed OS partitions are
copied into the existing disk. An unchanged build writes no disk partitions.

## Hardware scope and next steps

| Part | First diagnostic image | Android bring-up later |
|---|---|---|
| Ryzen 5 7530U | Source-based VEX GFNI/AVX-VNNI emulation + small boot self-test | Broader emulator correctness/performance testing |
| USB xHCI/storage/HID | Built into kernel | More device coverage |
| UEFI display | Firmware framebuffer console | `amdgpu`, Mesa RADV/GBM, minigbm |
| AMD GPIO / I2C HID | Compiled in; physical test still needed | ELAN0307 touchpad integration |
| MT7922 Wi-Fi / Bluetooth | Not enabled yet | `mt7921e`, `btusb`/`btmtk`, firmware |
| Audio | Not enabled yet | HDA + AMD ACP |
| Internal NVMe | Deliberately disabled | Explicit dev partition support later |

The hardware table describes the older diagnostic USB, not the QEMU GKI. Real-laptop Android
graphics, Wi-Fi, audio and USB deployment of Android remain separate work; no installer is added.

**Known emulator limitation:** the imported patch handles VEX GFNI, not legacy SSE-encoded
GFNI (the initial boot test confirmed that the latter raises SIGILL). The positive self-test
checks VEX `vgf2p8mulb` and `vpdpbusd` results, not every instruction/encoding or full Android
compatibility. Keep that distinction when evaluating new userspace binaries.

Validated locally: nine deployment/safety tests; UEFI QEMU boot through the source-built
GRUB/kernel; both supported instruction tests trapping into the emulator; saved USB logs;
clean poweroff; unchanged output timestamps on a no-op build; and no kernel/loader rebuild
for an initramfs-only change. Physical USB flashing and laptop boot are not claimed as tested.

## Source attribution

- Kernel: [Android common](https://android.googlesource.com/kernel/common/), GPL-2.0.
- BusyBox: [1.37.0](https://busybox.net/), GPL-2.0; upstream published SHA-256.
- GRUB: [2.12](https://www.gnu.org/software/grub/), GPL-3.0-or-later; hash also recorded by
  [Buildroot](https://github.com/buildroot/buildroot/blob/2024.02/boot/grub2/grub2.hash).
- Graphics: [Mesa](https://mesa3d.org/), [libdrm](https://dri.freedesktop.org/libdrm/) and
  [Expat](https://libexpat.github.io/), built from the pinned upstream sources and their licences.
- Development security HALs: unmodified binaries from Google's pinned Android 17 emulator
  image. Googlebook userspace remains proprietary recovery-image content, not a source rebuild
  or a claim of redistribution permission.
- Instruction-emulation source patch: [Project Churro, pinned revision](https://github.com/kesali/project-churro-msi-modern-15-B7M/blob/488dab956808916100eca141ee251a5a5773eeba/kmod/patches/vex-emulate.patch).
  Downloaded, checksum-verified and applied to kernel **source**, with the user's approval.
  The reference repository has no top-level licence; resolve redistribution permissions before
  publishing its patch or resulting images. This build does not vendor its implementation.

The two original working ports remain under ignored `reference/` for comparison. Their build
scripts and prebuilt kernels are not used. None of this pipeline edits executable bytes.
