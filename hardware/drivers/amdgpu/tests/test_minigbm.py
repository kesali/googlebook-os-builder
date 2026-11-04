"""Check AMD minigbm uses upstream Mesa backend selection."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[4]


class MinigbmBuildTests(unittest.TestCase):
    def test_build_uses_upstream_mesa_backend_selection(self):
        script = (ROOT / "scripts/minigbm.sh").read_text()
        flag_groups = re.findall(r'^flags\+="([^"]+)"$', script, re.MULTILINE)
        definitions = {flag for group in flag_groups for flag in group.split()}
        recipe = (ROOT / "hardware/drivers/amdgpu/minigbm.mk").read_text()

        self.assertIn("-DDRV_GBM_MESA", definitions)
        self.assertNotIn("-DDRV_MESA_AMDGPU", definitions)
        self.assertIn("-DDRV_I915", definitions)
        self.assertIn("-DDRV_XE", definitions)
        self.assertNotIn("minigbm-amd.patch", recipe)
        self.assertIn("minigbm-yuv-pitch.patch", recipe)

    def test_amd_profiles_select_mesa_through_upstream_vulkan_property(self):
        for profile in ("graphics-amd.rc", "graphics-amd-vulkan.rc"):
            with self.subTest(profile=profile):
                settings = (ROOT / "hardware/msi-modern-15-b7m/system_ext" / profile).read_text()
                self.assertIn("setprop ro.hardware.vulkan radeon", settings)


if __name__ == "__main__":
    unittest.main()
