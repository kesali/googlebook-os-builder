"""Check recipe-owned display density without booting a guest."""

from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand


class ChangeDataTests(unittest.TestCase):
    def test_laptop_density_is_set_only_for_the_laptop_panels(self):
        lenovo = (REPO / "hardware/lenovo-e50-80/system_ext/display-lenovo.rc").read_text()
        self.assertIn("on early-init && property:ro.boot.gbos_builder.graphics=intel\n"
                      "    setprop qemu.sf.lcd_density 160\n", lenovo)
        self.assertIn("etc/init/zz-gbos-builder-display-lenovo.rc",
                      expand(REPO / "android/system_ext/install.list"))


if __name__ == "__main__":
    unittest.main()
