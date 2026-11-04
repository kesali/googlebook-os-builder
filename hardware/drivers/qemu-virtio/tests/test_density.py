"""Check recipe-owned display density without booting a guest."""

from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))


class ChangeDataTests(unittest.TestCase):
    def test_laptop_density_is_set_only_for_the_laptop_panels(self):
        softpipe = (REPO / "hardware/drivers/qemu-virtio/system_ext/graphics-softpipe.rc").read_text()
        self.assertNotIn("qemu.sf.lcd_density", softpipe)


if __name__ == "__main__":
    unittest.main()
