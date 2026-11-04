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
        entry = front_camera_entry('0bda:579c', 'Lenovo E50-80 integrated EasyCamera')
        edited = patched_camera_table(self, 'hardware/lenovo-e50-80/vendor/camera-lenovo.patch')
        self.assertEqual(edited.count('key: "0bda:579c"'), 1)
        self.assertIn(entry, edited)
        self.assertEqual(edited.replace(entry, "", 1), original)


if __name__ == "__main__":
    unittest.main()
