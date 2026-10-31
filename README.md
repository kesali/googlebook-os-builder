# gbos-dali

A Googlebook OS (Android 17 "android-desktop") USB stick for the **MSI Modern 15 B7M**, built from
Google's official recovery image plus parts we build ourselves from source, with a build that a
person can read.

## Principles

1. **Google's recovery image is a read-only input.** We never edit bytes inside a binary.
2. **Everything we add is built from pinned source** (plus our patches) or is a plain text file
   (properties, init `.rc`, configs). Unmodified upstream prebuilts are allowed only where building
   from source would mean building all of AOSP; they are pinned by sha256.
3. **One script, one step.** Every script starts with a header saying what it reads and writes.
   Binary formats are handled by upstream tools (`unpack_bootimg`, `avbtool`, `mkfs.erofs`, ...) or
   by small Python tools in `tools/` that use the field names of the official format definitions.
4. **`make` knows what depends on what**, so only changed parts rebuild; updating the stick will
   rewrite only what changed (planned: `make deploy`).
5. **This laptop first.** More hardware is added later, one driver at a time.

## Quick start

Needs Linux, Docker, `make`, and about 10 GB free for now.

```sh
make            # list the targets
make builder    # once: the Docker image with every build tool (docker/Dockerfile)
make unpack     # recovery image -> out/google/   (under a minute on NVMe)
less out/google/inventory.txt
```

## Input

The recovery image of a Googlebook, `android-desktop_signed_recovery_image.bin` (about 19 GB,
inside a ~7.8 GB `recovery.zip`). Models and builds are listed at
<https://aluminium-os.com/googlebookos/>. Developed with the Lenovo Googlebook 15 (`ruby`) image.
Set its path in [config.mk](config.mk) (`RECOVERY_IMAGE`) or on the command line.

## How the build is organised

| Path | What it is |
|---|---|
| [Makefile](Makefile) | The whole pipeline: targets, and the files each one needs |
| [config.mk](config.mk) | Settings: recovery image path, output directory, builder image name |
| [docker/Dockerfile](docker/Dockerfile) | Every build tool, pinned, so the host needs only Docker and `make` |
| [scripts/](scripts/) | One script per build step |
| [tools/](tools/) | Small, readable helpers for binary formats |
| `out/` | Everything generated (not in git); safe to delete |
| `reference/` | The two working ports this project learns from (not in git, not used by the build) |

### Steps

- **`make unpack`** ([scripts/unpack.sh](scripts/unpack.sh)): copies the pieces we need out of the
  recovery image into `out/google/`: the boot images and their contents, the logical partitions
  inside `super` ([tools/lp.py](tools/lp.py)), Google's kernel version and config
  ([tools/kernel_info.py](tools/kernel_info.py)), every `build.prop`, checksums, and a one-page
  `inventory.txt`. Every later step reads from `out/google/`, never from the recovery image.

## Roadmap

1. [x] Skeleton, builder container, unpack + inventory of Google's image
2. [ ] Kernel from source at the exact version Google ships, with instruction emulation for the
       CPU features this Ryzen lacks (GFNI, AVX-VNNI) and this laptop's drivers; boot Google's
       unmodified system from USB with logs on the stick; `make usb` and `make deploy`
3. [ ] Graphics: Mesa (RADV, GBM) and minigbm from source, to a working desktop
4. [ ] Wi-Fi, Bluetooth, audio, touchpad
5. [ ] Safety: block Google's firmware flashing; setup without OTA; software security HALs
6. [ ] Later: install to the internal NVMe (dev partition), more devices

## Target hardware: MSI Modern 15 B7M

| Part | Device (PCI/USB ID) | Linux driver |
|---|---|---|
| CPU | AMD Ryzen 5 7530U (Zen 3: AVX2, SHA-NI, VAES; no GFNI, no AVX-VNNI) | instruction emulation needed |
| GPU | AMD Barcelo `1002:15e7` | `amdgpu` |
| Wi-Fi | MediaTek MT7922 `14c3:0616` | `mt7921e` |
| Bluetooth | MediaTek `0e8d:0616` (USB) | `btusb`, `btmtk` |
| Audio | Ryzen HD Audio `1022:15e3`, HDMI audio `1002:1637` | `snd_hda_intel` |
| Microphones | AMD Audio Coprocessor `1022:15e2` | `snd_rn_pci_acp3x` |
| Touchpad | ELAN0307 (I2C HID) | `i2c_hid_acpi` |
| Storage | Samsung PM9C1a NVMe `144d:a80d` | `nvme` |
| USB | Renoir/Cezanne xHCI `1022:1639` | `xhci_hcd` |

## Reference projects

`reference/` holds two ports that already boot on this laptop: **project-churro** (converts the
recovery image, kernel and graphics from source) and **gbos-x86** (fast stick updates, many
hardware lessons in its `HANDOFF.md`). Neither has a license file: reuse only our own changes from
them, or ask their authors first.
