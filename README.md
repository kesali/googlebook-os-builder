# gbos-builder

A small, readable builder for running **Googlebook OS (Android 17 desktop)** on laptops.
It starts from Google's pinned recovery image, uses upstream components where possible,
and keeps necessary changes in explicit hardware recipes, file lists and source patches.
No executable byte edits.

Developed on the **MSI Modern 15 B7M** and **Lenovo E50-80**, with QEMU as the regression
baseline. The aim is to make device bring-up understandable: inspect the hardware, add or
fix only what is missing, test it on the device, and share useful findings upstream.
Other laptops are not yet verified; automatic detection and easier device contributions
are future work, not features promised today.

**Personal project, not a supported distribution.** Back up your data and use at your own risk.
Software KeyMint/Gatekeeper are not hardware-protected; this is not a certified or
Play-Integrity device. SELinux stays enforcing.

## Current status

Owner-confirmed on the latest combined image (2026-11-04):

| Device | Verified |
|---|---|
| MSI Modern 15 B7M | USB boot/setup, Wi-Fi, keyboard/touchpad, speaker, microphone, camera preview/recording and Chrome; latest audio/camera regression is fine |
| Lenovo E50-80 | USB boot, Wi-Fi, keyboard/touchpad, Bluetooth, speaker, microphone, camera and Chrome; smaller UI at density 160 |
| QEMU | Inspected setup screen and input with Mesa softpipe and software security services; not accelerated graphics |

MSI graphics use ANGLE/RADV; Lenovo uses Iris GLES and hasvk Vulkan.
Headphones, brightness controls and suspend/resume still need checks.
MSI Bluetooth pairing is unconfirmed; HDMI audio is not implemented.
See the [component specs](docs/specs/README.md) for evidence and device-specific limitations.

CPU-portable BoringSSL makes Chrome launch and load pages faster on the Lenovo (owner report);
temporary touchpad capture is retired. QEMU checks pass; MSI regression after crypto is pending.

## Build and try in QEMU

Host requirements: Linux, Docker, GNU make, Python 3, `/dev/kvm` and a VNC viewer.
Allow at least **50 GB** for downloads/builds, plus the sparse Android data image.
The first build downloads large pinned inputs and may take hours; repeat builds reuse them.
Everything compiles inside the Debian builder container.

```sh
make                         # list targets
make test                    # fast unit tests; no physical disks or network
make qemu JOBS=12            # build and boot; VNC at localhost:5900
make qemu-check JOBS=12      # bounded regression check, then stop the VM
```

Inspect the saved [QEMU screenshot](out/qemu/screen.png); a printed PASS alone is not proof
of a usable screen. QEMU uses a software-rendered 1280x720 display by default.
Keep downloaded inputs and editable source trees under ignored `out/`.

## Run on a laptop

Use a **64 GB or larger USB**, preferably USB 3. The default image is about **49.8 GiB**.
Disable Secure Boot and select the USB's UEFI entry. The internal NVMe is hidden from Android.

For a fresh USB (**erases all existing USB data**):

```sh
make install-usb JOBS=12
```

The host tool asks you to select a USB by model, capacity and serial, confirm the erase,
and verifies the copied image. Physical deployment is the owner's operation, not an agent action.

For an existing compatible gbos-builder USB (**preserves apps, accounts and data**):

```sh
make update-usb JOBS=12
```

Before either command, stop any VM using the image and unmount the USB's partitions.
The updater checks the layout, writes only changed OS/boot content and verifies read-back;
it does not repartition or format. Older Dali or incompatible-layout media need an explicit
fresh flash, not an update. If interrupted, rerun the operation before booting.

For build-only, use `make android-image JOBS=12`; it updates the regular file
[out/gbos-builder/disk.img](out/gbos-builder/disk.img), not a physical disk.
Never delete that image to repair a failed build: it holds persistent Android data.
See the [deployment guide](docs/build-guide.md#laptop-test-image) for layouts and safeguards.

## Diagnose and add hardware

Android retains current and previous boot logs. Back in Linux, attach the USB, unmount
its partitions and run:

```sh
make laptop-logs
make hardware-check          # validate recipe wiring without an image build
```

Log retrieval is read-only and saves private evidence under ignored `out/laptop-logs/`.
Do not publish raw logs. The combined image selects drivers in
[hardware/drivers.list](hardware/drivers.list) and device configuration in
[hardware/devices.list](hardware/devices.list). Recipes are not yet independently selectable
laptop builds or a runtime driver installer.

## Documentation

- [Build and deployment guide](docs/build-guide.md): recipe format, USB details, source map,
  kernel ABI checks, Android changes, QEMU and the separate parked diagnostic OS.
- [Component specs](docs/specs/README.md): verified behavior, decisions and remaining checks.
- [Project plan](docs/plan.md): daily testing and the builder direction.
- [Design report](docs/report.md): historical explanation and comparison with the reference ports.
- [Patch audit](docs/patch-audit.md): each source patch checked against current upstream.
- [Agent guide](AGENTS.md): workflow and safety rules for AI-assisted work.

## License and sources

Original code and documentation use the [MIT License](LICENSE), **AS IS**, without warranty.
Google's image, third-party code and firmware retain their own licenses; this does not grant
redistribution rights. All downloads are pinned in [sources.mk](sources.mk).
See [source attribution](docs/build-guide.md#source-attribution), including the unresolved
redistribution permission for the reference instruction-emulation patch.
