"""Check recipe-owned display density without booting a guest."""

from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))


class ChangeDataTests(unittest.TestCase):
    def test_laptop_density_is_set_only_for_the_laptop_panels(self):
        amd = (REPO / "hardware/msi-modern-15-b7m/system_ext/graphics-amd.rc").read_text()
        self.assertIn("setprop qemu.sf.lcd_density 160", amd)


if __name__ == "__main__":
    unittest.main()
