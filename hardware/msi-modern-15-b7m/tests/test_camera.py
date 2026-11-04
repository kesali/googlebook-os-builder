"""Check this laptop camera declaration without opening a device."""

from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tests"))
from recipe_support import CAMERA_TABLE, front_camera_entry, patched_camera_table


class CameraConfigTests(unittest.TestCase):
    def test_each_laptop_adds_only_its_usb_id_without_borrowed_calibration(self):
        original = CAMERA_TABLE.read_text()
        entry = front_camera_entry('30c9:0042', 'MSI Modern 15 B7M integrated webcam')
        edited = patched_camera_table(self, 'hardware/msi-modern-15-b7m/vendor/camera-msi.patch')
        self.assertEqual(edited.count('key: "30c9:0042"'), 1)
        self.assertIn(entry, edited)
        self.assertEqual(edited.replace(entry, "", 1), original)


if __name__ == "__main__":
    unittest.main()
