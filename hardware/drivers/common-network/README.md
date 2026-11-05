# Common PC networking

Shared support, not a laptop profile. These additions are **build-checked; hardware untested**.
The combined image passes config/kABI, module signatures/imports/CRCs, dependencies, complete
aliases and image metadata/fit checks. Physical networking remains untested.

| Hardware / driver | Implementation | Remaining verification |
|---|---|---|
| Intel PCIe Ethernet, `e1000e` / `igc` | Reuse Google's signed modules, dependencies and PCI aliases unchanged | Physical link, DHCP and traffic on each adapter |
| Intel PCIe Ethernet, `igb` | Build/sign upstream module, install dependencies and native PCI aliases | Kernel ABI, compiled imports/dependencies, image and physical traffic |
| Realtek PCIe Ethernet, `r8169` | Reuse Google's module/aliases; supply missing requested `rtl_nic` firmware | Firmware read-back and physical link/traffic |
| Intel 3160/3168, 7260/7265, 8000C/8265, 9000/9260, AX200/201/210/211 families | Reuse Google's `iwlwifi`, `iwlmvm` and private `iwl7000_mac80211`; add matching firmware/API versions and applicable PNVM | Firmware read-back, binding, scan, connection and traffic; exact PCI/firmware variant matters |
| Realtek 8723DE, 8821CE, 8822BE/CE | Upstream `rtw88` PCI modules and matching runtime firmware | Compiled compatibility with Google's wireless helpers, image and physical Wi-Fi |
| Realtek 8851BE, 8852AE/BE/CE | Upstream `rtw89` PCI modules and matching firmware formats | Compiled compatibility with Google's wireless helpers, image and physical Wi-Fi |

The existing Ruby image already contains generic USB HID, storage/UAS, USB audio/UVC and
several USB Ethernet drivers. Their presence does not establish Android app support or tests
on every peripheral. They do not need duplicate replacement modules here.

## Why these files exist

- [gki.config](gki.config) enables only missing upstream modules and their default LED/sensor
  options. Google's config alone does not list all shipped drivers: its external signed modules
  include Ethernet and Intel Wi-Fi even where the embedded config says disabled.
- [modules.list](modules.list) and [vendor_dlkm.install](vendor_dlkm.install) use the existing
  signing and compiled import/CRC checks. Never replace Google's cfg80211/mac80211 or its
  private Intel wireless stack to force a driver to load.
- [modules.patch](vendor_dlkm/modules.patch) is generated from pristine Google module metadata;
  its PCI IDs follow the pinned upstream tables. Runtime hotplug uses these aliases rather
  than preloading drivers for hardware that may not be present. Entries are prepended:
  appending to the same original EOF as the existing laptop patch fails with `--fuzz=0`.
  The sequential-patch regression preserves both sets of entries without loosening checks.
- [firmware.list](firmware.list) selects unchanged blobs and their license notices from the
  already pinned linux-firmware archive. [vendor.install](vendor.install) maps Intel archive
  subdirectories to the root names requested by Google's driver.

Read-only inspection of the pinned recovery found 115 `e1000e`, 16 `igc`, 22 `r8169` and
299 `iwlwifi` PCI alias entries. Its Intel firmware mainly covers newer SC variants;
the additional files target older/common adapters advertised by the same module.
Realtek Ethernet had USB firmware but lacked the PCIe runtime blobs requested by `r8169`.
These findings establish packaging gaps, not successful hardware operation.

Firmware versions come from shipped `modinfo -F firmware` declarations for Intel/Realtek
Ethernet, and the pinned kernel's firmware-name/format constants for `rtw88`/`rtw89`.
See [upstream Intel documentation](https://wireless.docs.kernel.org/en/latest/en/users/drivers/iwlwifi.html).
No out-of-tree Realtek driver or new source/download pin is introduced.

Bluetooth halves of Intel/Realtek combination cards, USB/SDIO Realtek Wi-Fi, Wi-Fi 7 and
other firmware variants are not added by this recipe. Existing MSI/Lenovo support stays intact.
If Google's trimmed wireless exports cannot satisfy an upstream Realtek module, report the
specific mismatch; do not weaken ABI checks or quietly replace the shared wireless stack.

## Checks

57 focused recipe, hardware declaration, module checker and overlay tests pass. Unit tests
cover declarations, synthetic firmware extraction/refusals, unchanged repeat timestamps,
compiled-alias validation with fake metadata and sequential zero-fuzz metadata patches.
Read-only inspection of the pinned archive found all 60 selected firmware/license members
as nonempty regular files, with no symlink-target extraction needed.
[Test output](../../../out/common-network-inventory/tests.txt).
These checks do **not** establish module ABI compatibility or physical networking.
The combined kernel/image build now passes those checks, including Realtek against Google's
unchanged wireless helpers. 66 combined focused tests pass; normal/diagnostic QEMU reaches
inspected setup with enforcing SELinux, but does not exercise these physical adapters.
[Build and runtime evidence](../../../out/common-hardware-validation/).
