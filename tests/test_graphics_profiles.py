"""Keep the renderer choices explicit and the Vulkan HWUI option opt-in."""

from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
SYSTEM_EXT = REPO / "android/system_ext"


class GraphicsProfileTests(unittest.TestCase):
    def test_each_graphics_profile_sets_an_explicit_hwui_renderer(self):
        profiles = {
            "graphics-amd.rc": ("false", "skiagl"),
            "graphics-amd-vulkan.rc": ("true", "skiavk"),
            "graphics-softpipe.rc": ("false", "skiagl"),
        }
        install_list = (SYSTEM_EXT / "install.list").read_text()

        for name, (vulkan, renderer) in profiles.items():
            with self.subTest(profile=name):
                profile = (SYSTEM_EXT / name).read_text()
                self.assertIn(f"setprop ro.hwui.use_vulkan {vulkan}", profile)
                self.assertIn(f"setprop debug.hwui.renderer {renderer}", profile)
                self.assertIn(f"etc/dali/{name}", install_list)

    def test_vendor_build_props_leave_hwui_renderer_to_the_selected_profile(self):
        patch = (REPO / "android/vendor/build-prop.patch").read_text()
        self.assertIn("-ro.hwui.use_vulkan=true\n", patch)
        self.assertNotIn("+ro.hwui.use_vulkan=", patch)
        self.assertNotIn("+debug.hwui.renderer=", patch)

    def test_vulkan_hwui_menu_entry_is_opt_in_for_the_amd_gpu(self):
        menu = (REPO / "boot/android-menu.cfg").read_text()
        entry = 'if [ "$dali_graphics" = amd ]; then\n    menuentry "Googlebook OS (test: Vulkan HWUI)"'
        self.assertIn(entry, menu)
        self.assertIn("set dali_graphics=amd-vulkan", menu)
        self.assertIn("set default=0", menu)


if __name__ == "__main__":
    unittest.main()
