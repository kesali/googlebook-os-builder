"""Check the exact USB-camera configuration patch without opening a camera."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
CAMERA_TABLE = REPO / "tests/camera/internal_usb_camera_info.txtpb"
MSI_CAMERA = "hardware/msi-modern-15-b7m/vendor/camera-msi.patch"
LENOVO_CAMERA = "hardware/lenovo-e50-80/vendor/camera-lenovo.patch"


def front_camera_entry(usb_id, name):
    return (
        "camera_modules {\n"
        f'  key: "{usb_id}" # {name}\n'
        "  value {\n"
        "    facing: FACING_FRONT\n"
        "  }\n"
        "}\n"
    )


class CameraConfigTests(unittest.TestCase):
    def test_camera_service_clears_only_the_inherited_render_driver_override(self):
        fixture = REPO / "tests/camera/provider-usb.rc"
        original = fixture.read_text()
        setting = '    setenv MESA_LOADER_DRIVER_OVERRIDE ""\n'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = root / "etc/init/android.hardware.camera.provider-usb-service.android-desktop.rc"
            service.parent.mkdir(parents=True)
            shutil.copyfile(fixture, service)
            result = subprocess.run(
                ["patch", "--batch", "--fuzz=0", "-p1", "-i",
                 str(REPO / "hardware/drivers/amdgpu/vendor/camera-va-driver.patch")],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            edited = service.read_text()
        self.assertEqual(edited.count(setting), 1)
        self.assertEqual(edited.replace(setting, "", 1), original)
        service_block = edited.split("\non boot", 1)[0]
        self.assertIn(setting, service_block)
        for profile in ("graphics-amd.rc", "graphics-amd-vulkan.rc"):
            self.assertIn("    export MESA_LOADER_DRIVER_OVERRIDE zink\n",
                          (REPO / "hardware/msi-modern-15-b7m/system_ext" / profile).read_text())

    def patched_camera_table(self, *patches):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "etc/camera/internal_usb_camera_info.txtpb"
            config.parent.mkdir(parents=True)
            shutil.copyfile(CAMERA_TABLE, config)
            for patch_file in patches:
                result = subprocess.run(
                    ["patch", "--batch", "--fuzz=0", "-p1", "-i", str(REPO / patch_file)],
                    cwd=root, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return config.read_text()

    def test_each_laptop_adds_only_its_usb_id_without_borrowed_calibration(self):
        original = CAMERA_TABLE.read_text()
        for patch_file, usb_id, name in (
            (MSI_CAMERA, "30c9:0042", "MSI Modern 15 B7M integrated webcam"),
            (LENOVO_CAMERA, "0bda:579c", "Lenovo E50-80 integrated EasyCamera"),
        ):
            with self.subTest(usb_id=usb_id):
                entry = front_camera_entry(usb_id, name)
                edited = self.patched_camera_table(patch_file)
                self.assertEqual(edited.count(f'key: "{usb_id}"'), 1)
                self.assertIn(entry, edited)
                self.assertEqual(edited.replace(entry, "", 1), original)

    def test_both_laptop_camera_entries_apply_in_recipe_order(self):
        edited = self.patched_camera_table(MSI_CAMERA, LENOVO_CAMERA)
        self.assertIn(front_camera_entry("30c9:0042", "MSI Modern 15 B7M integrated webcam"), edited)
        self.assertIn(front_camera_entry("0bda:579c", "Lenovo E50-80 integrated EasyCamera"), edited)


if __name__ == "__main__":
    unittest.main()
