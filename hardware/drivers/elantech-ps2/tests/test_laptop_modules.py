"""Dependency metadata checks use fake module graphs."""

from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
from laptop_module_check import LAPTOP_ALIASES
from hardware_recipes import expand


class LaptopModuleTests(unittest.TestCase):
    def test_elantech_ps2_module_is_packaged_with_hotplug_and_builtin_helpers(self):
        config = expand(REPO / "kernel/gki.config")
        self.assertIn("CONFIG_MOUSE_PS2=m\n", config)
        self.assertIn("CONFIG_MOUSE_PS2_ELANTECH=y\n", config)
        self.assertIn("CONFIG_MOUSE_PS2_ELANTECH_SMBUS=y\n", config)
        self.assertIn("drivers/input/mouse/psmouse.ko",
                      expand(REPO / "kernel/laptop-modules.list").splitlines())
        installs = expand(REPO / "android/vendor_dlkm/install.list")
        self.assertIn("gki/psmouse.ko", installs)
        self.assertNotIn("gki/i2c-smbus.ko", installs)
        module_patch = (REPO / "hardware/drivers/laptop-modules/vendor_dlkm/modules.patch").read_text()
        self.assertIn("+/vendor/lib/modules/psmouse.ko:\n", module_patch)
        self.assertEqual(LAPTOP_ALIASES["psmouse"], "serio:ty01pr*id*ex*")
        self.assertIn("+alias serio:ty01pr*id*ex* psmouse\n", module_patch)


if __name__ == "__main__":
    unittest.main()
