"""Keep the AMD recipe limited to the selected desktop and Vulkan drivers."""

from pathlib import Path
import unittest

from hardware_recipes import expand


REPO = Path(__file__).resolve().parents[4]


class AmdMesaTests(unittest.TestCase):
    def test_recipe_installs_rendering_drivers_without_camera_va_support(self):
        script = (REPO / "scripts/mesa.sh").read_text()
        self.assertIn("-Dgallium-drivers=softpipe,zink,iris", script)
        self.assertIn("-Dvulkan-drivers=amd,intel_hasvk", script)
        self.assertIn("-Dgallium-va=disabled", script)
        self.assertNotIn("-Dgallium-drivers=radeonsi", script)

        installs = [line.split() for line in
                    expand(REPO / "hardware/drivers/amdgpu/vendor.install").splitlines()
                    if line and not line.startswith("#")]
        installed_names = {Path(line[0]).name for line in installs}
        self.assertNotIn("radeonsi_drv_video.so", installed_names)
        self.assertNotIn("libdrm_amdgpu.so", installed_names)
        self.assertIn("vulkan.radeon.so", installed_names)


if __name__ == "__main__":
    unittest.main()
