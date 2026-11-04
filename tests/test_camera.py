"""Check the exact USB-camera configuration patch without opening a camera."""

import unittest
from recipe_support import front_camera_entry, patched_camera_table

MSI_CAMERA = "hardware/msi-modern-15-b7m/vendor/camera-msi.patch"
LENOVO_CAMERA = "hardware/lenovo-e50-80/vendor/camera-lenovo.patch"
class CameraConfigTests(unittest.TestCase):
    def test_both_laptop_camera_entries_apply_in_recipe_order(self):
        edited = patched_camera_table(self, MSI_CAMERA, LENOVO_CAMERA)
        self.assertIn(front_camera_entry("30c9:0042", "MSI Modern 15 B7M integrated webcam"), edited)
        self.assertIn(front_camera_entry("0bda:579c", "Lenovo E50-80 integrated EasyCamera"), edited)


if __name__ == "__main__":
    unittest.main()
