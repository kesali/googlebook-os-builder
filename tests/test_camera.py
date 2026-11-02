"""Check the exact USB-camera configuration patch without opening a camera."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


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
                 str(REPO / "android/vendor/camera-va-driver.patch")],
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
                          (REPO / "android/system_ext" / profile).read_text())

    def test_only_msi_usb_id_is_added_without_borrowed_calibration(self):
        fixture = REPO / "tests/camera/internal_usb_camera_info.txtpb"
        original = fixture.read_text()
        entry = (
            "camera_modules {\n"
            '  key: "30c9:0042" # MSI Modern 15 B7M integrated webcam\n'
            "  value {\n"
            "    facing: FACING_FRONT\n"
            "  }\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "etc/camera/internal_usb_camera_info.txtpb"
            config.parent.mkdir(parents=True)
            shutil.copyfile(fixture, config)
            result = subprocess.run(
                ["patch", "--batch", "--fuzz=0", "-p1", "-i",
                 str(REPO / "android/vendor/camera-msi.patch")],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            edited = config.read_text()
        self.assertEqual(edited.count('key: "30c9:0042"'), 1)
        self.assertIn(entry, edited)
        self.assertEqual(edited.replace(entry, "", 1), original)


if __name__ == "__main__":
    unittest.main()
