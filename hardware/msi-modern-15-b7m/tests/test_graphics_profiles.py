"""Keep the renderer choices explicit and the Vulkan HWUI option opt-in."""

from pathlib import Path
import unittest
import sys

REPO = Path(__file__).resolve().parents[3]
SYSTEM_EXT = REPO / "android/system_ext"
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand


class GraphicsProfileTests(unittest.TestCase):
    def test_vulkan_hwui_menu_entry_is_opt_in_for_the_amd_gpu(self):
        menu = (REPO / "boot/android-menu.cfg").read_text()
        entry = 'if [ "$gbos_builder_graphics" = amd ]; then\n    menuentry "Googlebook OS (test: Vulkan HWUI)"'
        self.assertIn(entry, menu)
        self.assertIn("set gbos_builder_graphics=amd-vulkan", menu)
        self.assertIn("set default=android-berberis", menu)
        self.assertIn("set default=android-houdini", menu)


if __name__ == "__main__":
    unittest.main()
