"""Keep the renderer choices explicit and the Vulkan HWUI option opt-in."""

from pathlib import Path
import unittest
import sys

REPO = Path(__file__).resolve().parents[4]
SYSTEM_EXT = REPO / "android/system_ext"
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand


def profile_path(name):
    entries = [line.split() for line in expand(SYSTEM_EXT / "install.list").splitlines()
               if line.strip() and not line.startswith("#")]
    source = next(entry[4] for entry in entries if entry[0] == f"etc/gbos-builder/{name}")
    return REPO / source


class GraphicsProfileTests(unittest.TestCase):
    def test_broadwell_profile_renders_with_gl_and_offers_hasvk_to_apps(self):
        profile = profile_path("graphics-intel-hasvk.rc").read_text()
        self.assertIn("setprop ro.hardware.egl mesa", profile)
        self.assertIn("setprop ro.hardware.vulkan intel_hasvk", profile)
        self.assertIn("setprop ro.hwui.use_vulkan false", profile)
        self.assertIn("setprop debug.renderengine.vulkan false", profile)
        self.assertIn("export GALLIUM_DRIVER iris", profile)
        self.assertIn("sys.gbos_builder.graphics=intel-hasvk", profile)
        for override in ("LIBGL_ALWAYS_SOFTWARE", "zink", "radv"):
            self.assertNotIn(override, profile)

    def test_gen9_and_newer_profile_selects_anv_without_changing_hwui(self):
        profile = profile_path("graphics-intel-anv.rc").read_text()
        self.assertIn("setprop ro.hardware.vulkan intel", profile)
        self.assertIn("setprop ro.hwui.use_vulkan false", profile)
        self.assertIn("setprop debug.renderengine.vulkan false", profile)
        self.assertIn("sys.gbos_builder.graphics=intel-anv", profile)
        install = (REPO / "hardware/drivers/i915/vendor.install").read_text()
        self.assertIn("lib64/hw/vulkan.intel_hasvk.so", install)
        self.assertNotIn("lib64/hw/vulkan.intel.so ", install)
        menu = (REPO / "boot/android-menu.cfg").read_text()
        self.assertIn('setpci -d 8086:1616 -v gbos_builder_gpu VENDOR_ID', menu)
        self.assertIn('if [ "$gbos_builder_gpu" = "8086" ]; then\n'
                      '    set gbos_builder_device_profile=lenovo\nfi', menu)
        self.assertIn("setpci -d 1002:15e7", menu)
        self.assertIn('set gbos_builder_device_profile=none', menu)


if __name__ == "__main__":
    unittest.main()
