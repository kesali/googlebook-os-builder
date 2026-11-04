"""Keep AMD on GL HWUI without an unsupported Vulkan GRUB choice."""

from pathlib import Path
import unittest
import sys

REPO = Path(__file__).resolve().parents[3]
SYSTEM_EXT = REPO / "android/system_ext"
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand


class GraphicsProfileTests(unittest.TestCase):
    def test_gl_hwui_is_default_for_amd_without_a_vulkan_grub_choice(self):
        menu = (REPO / "boot/android-menu.cfg").read_text()
        profile = (REPO / "hardware/msi-modern-15-b7m/system_ext/graphics-amd.rc").read_text()
        install_list = (REPO / "hardware/msi-modern-15-b7m/system_ext.install").read_text()

        self.assertIn("setprop ro.hwui.use_vulkan false", profile)
        self.assertIn("setprop debug.hwui.renderer skiagl\n", profile)
        self.assertIn("setprop debug.renderengine.vulkan true", profile)
        self.assertIn("setprop debug.renderengine.backend skiavkthreaded", profile)
        self.assertNotIn("Vulkan HWUI", menu)
        self.assertNotIn("graphics-amd-vulkan", menu)
        self.assertNotIn("amd-vulkan", menu)
        self.assertNotIn("graphics-amd-vulkan", install_list)
        self.assertFalse((REPO / "hardware/msi-modern-15-b7m/system_ext/"
                          "graphics-amd-vulkan.rc").exists())
        self.assertIn("set default=android-berberis", menu)
        self.assertIn("set default=android-houdini", menu)


if __name__ == "__main__":
    unittest.main()
