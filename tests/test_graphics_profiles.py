"""Keep the renderer choices explicit and the Vulkan HWUI option opt-in."""

from pathlib import Path
import unittest
import sys

REPO = Path(__file__).resolve().parents[1]
SYSTEM_EXT = REPO / "android/system_ext"
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand


def profile_path(name):
    entries = [line.split() for line in expand(SYSTEM_EXT / "install.list").splitlines()
               if line.strip() and not line.startswith("#")]
    source = next(entry[4] for entry in entries if entry[0] == f"etc/gbos-builder/{name}")
    return REPO / source


class GraphicsProfileTests(unittest.TestCase):

    def test_each_graphics_profile_sets_an_explicit_hwui_renderer(self):
        profiles = {
            "graphics-amd.rc": ("false", "skiagl"),
            "graphics-amd-vulkan.rc": ("true", "skiavk"),
            "graphics-softpipe.rc": ("false", "skiagl"),
            "graphics-intel.rc": ("false", "skiagl"),
        }
        install_list = expand(SYSTEM_EXT / "install.list")

        for name, (vulkan, renderer) in profiles.items():
            with self.subTest(profile=name):
                profile = profile_path(name).read_text()
                self.assertIn(f"setprop ro.hwui.use_vulkan {vulkan}", profile)
                self.assertIn(f"setprop debug.hwui.renderer {renderer}", profile)
                self.assertIn(f"etc/gbos-builder/{name}", install_list)

    def test_vendor_build_props_leave_hwui_renderer_to_the_selected_profile(self):
        patch = (REPO / "android/vendor/build-prop.patch").read_text()
        self.assertIn("-ro.hwui.use_vulkan=true\n", patch)
        self.assertNotIn("+ro.hwui.use_vulkan=", patch)
        self.assertNotIn("+debug.hwui.renderer=", patch)


    def test_software_codec_sandbox_allows_only_the_mesa_affinity_query(self):
        vendor = REPO / "android/vendor"
        policy = (vendor / "mediaswcodec.policy").read_text()
        rules = [line.strip() for line in policy.splitlines()
                 if line.strip() and not line.startswith("#")]
        self.assertEqual(rules, ["sched_getaffinity: 1"])
        installs = [line.split() for line in (vendor / "install.list").read_text().splitlines()
                    if line.strip() and not line.startswith("#")]
        self.assertIn(
            ["etc/seccomp_policy/mediaswcodec.policy", "0644", "0:0",
             "vendor_configs_file", "./mediaswcodec.policy"],
            installs,
        )

    def test_berberis_is_default_without_a_translator_specific_grub_entry(self):
        menu = (REPO / "boot/android-menu.cfg").read_text()
        self.assertIn('menuentry "Googlebook OS" {\n    boot_android\n}', menu)
        self.assertNotIn("native_bridge=", menu)
        self.assertNotIn("Berberis ARM translation", menu)
        self.assertIn("set default=0\n", menu)
        init = (SYSTEM_EXT / "gbos-builder.rc").read_text()
        early_init = init.split("on early-init\n", 1)[1]
        self.assertIn("    setprop ro.dalvik.vm.native.bridge "
                      "${ro.boot.gbos_builder.native_bridge:-libndk_translation.so}\n", early_init)
        patch = (REPO / "android/system/native-bridge.patch").read_text()
        changes = [line for line in patch.splitlines()
                   if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
        self.assertEqual(changes, ["-ro.dalvik.vm.native.bridge=libhoudini.so"])


if __name__ == "__main__":
    unittest.main()
