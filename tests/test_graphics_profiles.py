"""Keep the renderer choices explicit and the Vulkan HWUI option opt-in."""

from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
SYSTEM_EXT = REPO / "android/system_ext"


class GraphicsProfileTests(unittest.TestCase):
    def test_broadwell_profile_is_gl_only_and_does_not_select_amd_or_software(self):
        profile = (SYSTEM_EXT / "graphics-intel.rc").read_text()
        self.assertIn("setprop ro.hardware.egl mesa", profile)
        self.assertIn("setprop ro.hardware.vulkan none", profile)
        self.assertIn("setprop debug.renderengine.vulkan false", profile)
        self.assertIn("export GALLIUM_DRIVER iris", profile)
        for override in ("LIBGL_ALWAYS_SOFTWARE", "zink", "radv"):
            self.assertNotIn(override, profile)
        menu = (REPO / "boot/android-menu.cfg").read_text()
        self.assertIn('setpci -d 8086:1616 -v dali_gpu VENDOR_ID', menu)
        self.assertIn('if [ "$dali_gpu" = "8086" ]; then\n    set dali_graphics=intel\nfi', menu)
        self.assertIn("setpci -d 1002:15e7", menu)
        self.assertIn("set dali_graphics=softpipe", menu)

    def test_each_graphics_profile_sets_an_explicit_hwui_renderer(self):
        profiles = {
            "graphics-amd.rc": ("false", "skiagl"),
            "graphics-amd-vulkan.rc": ("true", "skiavk"),
            "graphics-softpipe.rc": ("false", "skiagl"),
            "graphics-intel.rc": ("false", "skiagl"),
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

    def test_berberis_entry_changes_only_the_native_bridge(self):
        menu = (REPO / "boot/android-menu.cfg").read_text()
        self.assertIn('menuentry "Googlebook OS" {\n    boot_android\n}', menu)
        self.assertIn(
            'menuentry "Googlebook OS (test: Berberis ARM translation)" {\n'
            '    boot_android androidboot.dali.native_bridge=libndk_translation.so\n}',
            menu,
        )
        self.assertIn("set default=0\n", menu)
        init = (SYSTEM_EXT / "dali.rc").read_text()
        early_init = init.split("on early-init\n", 1)[1]
        self.assertIn("    setprop ro.dalvik.vm.native.bridge "
                      "${ro.boot.dali.native_bridge:-libhoudini.so}\n", early_init)
        patch = (REPO / "android/system/native-bridge.patch").read_text()
        changes = [line for line in patch.splitlines()
                   if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
        self.assertEqual(changes, ["-ro.dalvik.vm.native.bridge=libhoudini.so"])


if __name__ == "__main__":
    unittest.main()
