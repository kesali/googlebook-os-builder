# gbos-dali

A small, readable build for developing a Googlebook OS port on the **MSI Modern 15 B7M**.
Google's recovery image is a read-only input, not something we patch with byte offsets.

**Current runnable target: a diagnostic USB, not an Android desktop.** It builds the kernel,
BusyBox and GRUB from pinned source, boots a shell, tests this Ryzen's missing CPU instructions,
and saves logs on the USB. Android userspace, AMD graphics and software security integration are
the next step. The diagnostic kernel is **not GKI-module-compatible**; do not combine it with
Google's prebuilt vendor modules.

## Build and boot

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
| [config.mk](config.mk) | Output path, jobs, recovery path, USB mountpoint |
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

Before Android is enabled: source-built graphics, safe text-level init/fstab/property changes,
firmware-updater exclusion, software KeyMint/Gatekeeper (unmodified SHA-256-pinned upstream
prebuilts were approved), and a tested data/partition layout. A diagnostic boot is not evidence
that Android or the physical laptop's entire hardware stack works.

**Known emulator limitation:** the imported patch handles VEX GFNI, not legacy SSE-encoded
GFNI (the initial boot test confirmed that the latter raises SIGILL). The positive self-test
checks VEX `vgf2p8mulb` and `vpdpbusd` results, not every instruction/encoding or full Android
compatibility. Keep that distinction when evaluating new userspace binaries.

Validated locally: nine deployment/safety tests; UEFI QEMU boot through the source-built
GRUB/kernel; both supported instruction tests trapping into the emulator; saved USB logs;
clean poweroff; unchanged output timestamps on a no-op build; and no kernel/loader rebuild
for an initramfs-only change. Physical USB flashing, laptop boot and Android startup are not
claimed as tested.

## Source attribution

- Kernel: [Android common](https://android.googlesource.com/kernel/common/), GPL-2.0.
- BusyBox: [1.37.0](https://busybox.net/), GPL-2.0; upstream published SHA-256.
- GRUB: [2.12](https://www.gnu.org/software/grub/), GPL-3.0-or-later; hash also recorded by
  [Buildroot](https://github.com/buildroot/buildroot/blob/2024.02/boot/grub2/grub2.hash).
- Instruction-emulation source patch: [Project Churro, pinned revision](https://github.com/kesali/project-churro-msi-modern-15-B7M/blob/488dab956808916100eca141ee251a5a5773eeba/kmod/patches/vex-emulate.patch).
  Downloaded, checksum-verified and applied to kernel **source**, with the user's approval.
  The reference repository has no top-level licence; resolve redistribution permissions before
  publishing its patch or resulting images. This build does not vendor its implementation.

The two original working ports remain under ignored `reference/` for comparison. Their build
scripts and prebuilt kernels are not used. None of this pipeline edits executable bytes.
