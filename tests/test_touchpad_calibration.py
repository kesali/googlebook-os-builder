"""Check the Lenovo palm-width override without opening input devices."""

from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand


class ElantechCalibrationTests(unittest.TestCase):
    def test_device_named_override_changes_only_single_contact_palm_width(self):
        device_name = "ETPS/2 Elantech Touchpad"
        filename = "".join(character if character.isascii() and (
            character.isalnum() or character in "-_") else "_"
                           for character in device_name) + ".idc"
        self.assertEqual(filename, "ETPS_2_Elantech_Touchpad.idc")
        calibration = REPO / "hardware/lenovo-e50-80/vendor" / filename
        settings = [line.strip() for line in calibration.read_text().splitlines()
                    if line.strip() and not line.startswith("#")]
        self.assertEqual(settings, ["gestureProp.Palm_Width = 50.0"])
        # Captured single-finger widths fit below the unchanged 75 mm multi-palm limit.
        threshold = float(settings[0].split("=")[1])
        self.assertGreater(threshold, 1540 / 32)
        self.assertGreater(threshold, 1078 / 32)
        self.assertLess(threshold, 75.0)
        entries = [line.split() for line in expand(REPO / "android/vendor/install.list").splitlines()
                   if line.strip() and not line.startswith("#")]
        self.assertIn([f"usr/idc/{filename}", "0644", "0:0",
                       "vendor_configs_file", f"hardware/lenovo-e50-80/vendor/{filename}"], entries)


if __name__ == "__main__":
    unittest.main()
