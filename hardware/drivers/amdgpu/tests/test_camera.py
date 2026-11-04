"""Check the exact USB-camera configuration patch without opening a camera."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[4]


class CameraConfigTests(unittest.TestCase):
    def test_camera_service_clears_only_the_inherited_render_driver_override(self):
        fixture = REPO / "hardware/drivers/amdgpu/tests/fixtures/provider-usb.rc"
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


if __name__ == "__main__":
    unittest.main()
