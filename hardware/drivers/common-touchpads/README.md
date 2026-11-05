# Common touchpad support

Shared controller/transport support, not a laptop profile. New additions are
**build-checked; hardware untested**: the added modules pass config/kABI, signed-module
imports/CRCs, dependencies and complete aliases against Google's unchanged helpers.
Audio configuration is unchanged.

## What is already included

Inspect the shipped modules, not just Google's embedded kernel config: external drivers can
be present even where that config says disabled.

| Path | Existing coverage | Verification limit |
|---|---|---|
| PS/2 | [psmouse](../elantech-ps2/gki.config): Elantech, Synaptics, ALPS, TrackPoint and other upstream protocols | Lenovo Elantech movement owner-confirmed; other protocols hardware untested |
| Standard HID over I2C | Google's built-in HID multitouch plus our [ACPI I2C-HID/DesignWare settings](../../../kernel/gki.config) | MSI touchpad owner-confirmed; other devices untested |
| Native Elan I2C | Google's `elan_i2c` module and ACPI aliases | Included unchanged; hardware untested |
| Cypress I2C | Google's `cyapatp` module, CRC helper and aliases | Included unchanged; hardware untested |
| Synaptics HID-RMI | Google's `hid-rmi` and `rmi_core` | Included unchanged; hardware untested |
| Intel I2C/controller glue | Google's Intel LPSS ACPI/PCI, DesignWare PCI, i801 SMBus and newer Intel pinctrl modules | Included unchanged; not a claim that every Intel controller works |

Read-only inspection of the pinned recovery confirmed these module/dependency/alias records.
Its `rmi_core` also contains the F03/F11/F12/F30/F3A handlers, including pointing and button
support. No replacement core is needed merely to add a transport.

## What this recipe adds

- **Haswell/Broadwell GPIO interrupts:** upstream `pinctrl-lynxpoint` for ACPI `INT33C7` /
  `INT3437`, plus its native `platform:lp_gpio` alias. It uses Google's `pinctrl-intel` helper.
  This supplies a missing controller used by some I2C touchpads, not a touchpad-specific quirk.
- **Synaptics RMI4 SMBus:** upstream `rmi_smbus`, its `i2c:rmi4_smbus` alias and Google's
  existing `rmi_core`. The existing psmouse Synaptics discovery can instantiate that client.

[gki.config](gki.config), [modules.list](modules.list) and
[vendor_dlkm.install](vendor_dlkm.install) use the existing signing, collision refusal and
symbol/CRC checks. `RMI4_CORE=m` enables compiling the new transport against upstream headers;
the newly built core is deliberately not published over Google's.
[modules.patch](vendor_dlkm/modules.patch) is generated from pristine Google metadata using
interior context, separate from the network and laptop patches. Compiled-module validation
requires every native alias for these two added modules, without broadening i915's scope.
No new firmware, upstream source patch, forced preload or driver parameter is introduced.

## Behavior and limits

Upstream Synaptics discovery and fallback remain unchanged. Completing SMBus support may let
compatible Synaptics pads use their native transport rather than PS/2; this needs a physical
regression test. No `synaptics_intertouch=1` override or new device allowlist is added.
The [Elantech/PS2 settings](../elantech-ps2/gki.config) and Google's native Elan module are
unchanged; this does not enable a new Elantech companion configuration.

This is not blanket support for every touchpad, gesture or palm-rejection mode. ACPI resources,
interrupt routing, firmware quirks and Android input classification can still need device
evidence. Plain RMI I2C/SPI transports and unrelated controller generations are not added
without a concrete need. No ALSA or Android audio routing changes belong here.

## Verification

62 focused touchpad/network recipe, module checker, hardware declaration and overlay tests
pass via `scripts/builder.sh python3 tools/run_tests.py` with explicit test paths.
[Test output](../../../out/common-touchpads-inventory/tests.txt).
The recipe tests use fake modinfo and small original-text fixtures to cover signing/dependencies,
complete aliases and zero-fuzz coexistence of all selected metadata patches. A separate
temporary-tree check applied the three patches to actual pristine Google metadata with zero
fuzz and preserved every original entry in order. Seven local documentation links resolve.
These checks do not establish compiled helper compatibility.

The combined build passes these checks and image metadata/fit. 66 combined focused tests pass.
A 24.3 s repeat preserves all 67 tracked published sizes/timestamps with no partition/boot
writes. Normal/diagnostic QEMU setup screens and keyboard focus response are inspected;
this does not exercise physical touchpad drivers.
[Evidence](../../../out/common-hardware-validation/).
Require owner-confirmed binding and input before marking a new device hardware-tested.
