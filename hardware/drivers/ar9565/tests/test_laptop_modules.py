"""Dependency metadata checks use fake module graphs."""

from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
from laptop_module_check import LAPTOP_ALIASES
from hardware_recipes import expand


class LaptopModuleTests(unittest.TestCase):
    def test_ar9565_uses_upstream_modules_without_replacing_google_wireless_helpers(self):
        config = expand(REPO / "kernel/gki.config")
        paths = expand(REPO / "kernel/laptop-modules.list").splitlines()
        installs = expand(REPO / "android/vendor_dlkm/install.list")
        for option in ("ATH_COMMON", "ATH9K", "ATH9K_HW", "ATH9K_COMMON"):
            self.assertIn(f"CONFIG_{option}=m\n", config)
        for path in ("drivers/net/wireless/ath/ath.ko",
                     "drivers/net/wireless/ath/ath9k/ath9k_hw.ko",
                     "drivers/net/wireless/ath/ath9k/ath9k_common.ko",
                     "drivers/net/wireless/ath/ath9k/ath9k.ko"):
            self.assertIn(path, paths)
            self.assertIn(f"gki/{Path(path).name}", installs)
        for name in ("cfg80211.ko", "mac80211.ko"):
            self.assertNotIn(f"gki/{name}", installs)
            self.assertFalse(any(Path(path).name == name for path in paths))
        module_patch = (REPO / "hardware/drivers/laptop-modules/vendor_dlkm/modules.patch").read_text()
        alias = "pci:v0000168Cd00000036sv*sd*bc*sc*i*"
        self.assertEqual(LAPTOP_ALIASES["ath9k"], alias)
        self.assertIn(f"+alias {alias} ath9k\n", module_patch)
    def test_ar3012_bluetooth_gets_ath3k_firmware_without_replacing_google_btusb(self):
        config = expand(REPO / "kernel/gki.config")
        paths = expand(REPO / "kernel/laptop-modules.list").splitlines()
        installs = expand(REPO / "android/vendor_dlkm/install.list")
        firmware = expand(REPO / "kernel/firmware.list").splitlines()
        vendor = expand(REPO / "android/vendor/install.list")
        self.assertIn("CONFIG_BT_ATH3K=m\n", config)
        self.assertIn("drivers/bluetooth/ath3k.ko", paths)
        self.assertIn("gki/ath3k.ko", installs)
        self.assertNotIn("gki/btusb.ko", installs)
        self.assertFalse(any(Path(path).name == "btusb.ko" for path in paths))
        for name in ("ar3k/AthrBT_0x31010000.dfu", "ar3k/ramps_0x31010000_40.dfu"):
            self.assertIn(name, firmware)
            self.assertIn(f"firmware/{name}", vendor)
        module_patch = (REPO / "hardware/drivers/laptop-modules/vendor_dlkm/modules.patch").read_text()
        alias = "usb:v0CF3p3004d*dc*dsc*dp*ic*isc*ip*in*"
        self.assertEqual(LAPTOP_ALIASES["ath3k"], alias)
        self.assertEqual([line for line in module_patch.splitlines()
                          if line.startswith("+alias ") and line.endswith(" ath3k")],
                         [f"+alias {alias} ath3k"])
        self.assertIn("+/vendor/lib/modules/ath3k.ko: /system/lib/modules/bluetooth.ko "
                      "/system/lib/modules/rfkill.ko\n", module_patch)
        self.assertIn("+options ath9k btcoex_enable=1\n", module_patch)


if __name__ == "__main__":
    unittest.main()
