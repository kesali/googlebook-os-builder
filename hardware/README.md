# Hardware support

Start with the [recipe guide](../docs/build-guide.md#hardware-recipes).

## Where does my change belong?

| Change | Location |
|---|---|
| Only kernel options, without extra files | [Shared kernel config](../kernel/gki.config), grouped with a short reason |
| Reusable driver support needing patches, firmware, module packaging or tests | A recipe under [drivers/](drivers/) |
| Laptop-specific settings or quirks | A device recipe, such as [Lenovo](lenovo-e50-80/) or [MSI](msi-modern-15-b7m/) |

Simple kernel options do not need their own driver directory. A dedicated driver recipe does
not require source patches: firmware or module packaging can justify one too.

[drivers.list](drivers.list) and [devices.list](devices.list) select the combined image's
recipes. Shared kernel options apply to every build. Adding a recipe also requires its native
fragments to be wired into the appropriate base lists; follow the guide rather than copying
an entire laptop's configuration.

Put recipe-specific tests and fixtures in that recipe's `tests/` directory. `make hardware-check`
checks declarations; `make test` runs generic tests and all recipe tests, including unselected
recipes. Neither proves that hardware works: record physical results and limitations separately.

## Included drivers and verification

Common upstream support belongs in shared configuration or reusable driver recipes, not a
new device recipe for every laptop. Include required firmware, signed modules, dependencies
and discovery aliases together; reserve device recipes for actual laptop-specific integration.
Additional common drivers can be selected individually; this table does not enable any.

Use these verification labels:

- **Hardware-tested:** the owner confirmed the named function on the named machine.
  This does not establish support for every device handled by the driver.
- **Build-checked; hardware untested:** the relevant configuration, module signatures,
  dependencies, firmware and aliases have been checked where applicable, but no physical
  functional result is recorded. State which checks actually ran; inclusion alone is not enough.
- **Included; validation pending:** declared for the image, without completed build checks.
- **Emulator-tested:** verified in QEMU, not evidence for physical hardware.

The table summarizes earlier verified images; it is not a claim that the latest unbuilt image
has been retested. Detailed evidence and outstanding physical checks are in the
[hardware spec](../docs/specs/laptop-hardware.md) and [QEMU spec](../docs/specs/qemu.md).

| Included driver/support | Verification | Limits / remaining checks |
|---|---|---|
| [amdgpu](drivers/amdgpu/) | Hardware-tested: MSI Modern 15 B7M display/video | Other AMD GPUs untested; HDMI frame rate not measured |
| [i915](drivers/i915/) | Hardware-tested: Lenovo E50-80 Broadwell graphics | Other Intel GPUs untested; AV1 playback does not prove hardware decoding |
| AMD DesignWare I2C-HID ([shared config](../kernel/gki.config)) | Hardware-tested: MSI touchpad | Other I2C-HID laptops untested |
| [PS/2 Elantech](drivers/elantech-ps2/) | Hardware-tested: Lenovo touchpad movement | Palm rejection unverified; other enabled PS/2 protocols hardware untested |
| [MT7922 / mt7921e](drivers/mt7922/) | Hardware-tested: MSI Wi-Fi | MSI Bluetooth firmware included/build-checked, pairing unverified; other supported adapters untested |
| [AR9565 / ath9k and ath3k](drivers/ar9565/) | Hardware-tested: Lenovo Wi-Fi and Bluetooth | Other supported adapters untested |
| [HDA audio integration](drivers/hda-audio/) | Hardware-tested: MSI speakers; Lenovo speakers/microphone | MSI headphone/headset microphone unverified; HDMI audio not implemented |
| [Renoir ACP](drivers/renoir-acp/) | Hardware-tested: MSI built-in microphone | Recording quality not measured; other ACP hardware untested |
| [QEMU virtio](drivers/qemu-virtio/) | Emulator-tested: graphics, input and network DHCP | No physical-hardware claim; full networking/setup remains unverified |

Other devices supported by an included driver are **hardware untested**, not automatically
supported: module aliases, firmware coverage and Android userspace integration may still differ.
When adding an untested candidate, give it its own row with the specific hardware/function,
completed build checks and remaining verification. Update that row when the owner tests it;
do not promote the entire driver family based on one device.
