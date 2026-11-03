"""Dependency metadata checks use fake module graphs."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from laptop_module_check import check, dependency_closure, LAPTOP_ALIASES


class LaptopModuleTests(unittest.TestCase):
    def test_includes_transitive_dependencies(self):
        graph = {"video.ko": ["wmi.ko"], "wmi.ko": [], "hwmon.ko": []}
        self.assertEqual(dependency_closure(["video.ko", "hwmon.ko"], graph), set(graph))

    def test_missing_dependency_is_not_ignored(self):
        with self.assertRaisesRegex(ValueError, "missing.ko"):
            dependency_closure(["video.ko"], {"video.ko": ["missing.ko"]})

    def test_empty_dependencies_need_no_extra_modules(self):
        self.assertEqual(dependency_closure([], {}), set())

    def test_system_dlkm_modules_are_leaves(self):
        graph = {"mac80211.ko": ["cfg80211.ko", "rfkill.ko"], "cfg80211.ko": ["rfkill.ko"]}
        self.assertEqual(dependency_closure(["mac80211.ko"], graph, {"rfkill.ko"}),
                         {"mac80211.ko", "cfg80211.ko", "rfkill.ko"})

    def test_vendor_modules_still_need_an_entry(self):
        with self.assertRaisesRegex(ValueError, "missing.ko"):
            dependency_closure(["video.ko"], {"video.ko": ["missing.ko"]}, {"rfkill.ko"})

    def test_microphone_modules_are_modular_and_installed_without_replacing_dmic(self):
        config = (REPO / "kernel/gki.config").read_text()
        for option in ("SND_SOC_AMD_RENOIR", "SND_SOC_AMD_RENOIR_MACH",
                       "SND_AMD_ACP_CONFIG", "SND_SOC_DMIC"):
            self.assertIn(f"CONFIG_{option}=m\n", config)
        paths = {line for line in (REPO / "kernel/laptop-modules.list").read_text().splitlines()
                 if line and not line.startswith("#")}
        installs = [line.split() for line in
                    (REPO / "android/vendor_dlkm/install.list").read_text().splitlines()
                    if line and not line.startswith("#")]
        for path in ("sound/soc/amd/snd-acp-config.ko",
                     "sound/soc/amd/renoir/snd-rn-pci-acp3x.ko",
                     "sound/soc/amd/renoir/snd-acp3x-pdm-dma.ko",
                     "sound/soc/amd/renoir/snd-acp3x-rn.ko"):
            with self.subTest(path=path):
                self.assertIn(path, paths)
                name = Path(path).name
                self.assertIn([f"lib/modules/{name}", "0644", "0:0",
                               "vendor_kernel_modules", f"gki/{name}"], installs)
        self.assertFalse(any(Path(path).name == "snd-soc-dmic.ko" for path in paths))

    def test_alias_check_uses_compiled_module_name_not_hyphenated_filename(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = root / "lib/modules"
            modules.mkdir(parents=True)
            installs = root / "install.list"
            installs.write_text("")
            (modules / "modules.dep").write_text("")
            alias_file = modules / "modules.alias"
            alias_file.write_text("".join(
                f"alias {alias} {name.replace('-', '_')}\n"
                for name, alias in LAPTOP_ALIASES.items()))

            def modinfo(arguments, text):
                self.assertTrue(text)
                name = Path(arguments[-1]).stem
                if arguments[2] == "alias":
                    return LAPTOP_ALIASES[name] + "\n"
                self.assertEqual(arguments[2], "name")
                return name.replace("-", "_") + "\n"

            with patch("laptop_module_check.subprocess.check_output", side_effect=modinfo):
                check(root, installs)
                alias_file.write_text(alias_file.read_text().replace(
                    "platform:acp_pdm_mach snd_acp3x_rn",
                    "platform:acp_pdm_mach snd-acp3x-rn"))
                with self.assertRaisesRegex(ValueError, "snd-acp3x-rn"):
                    check(root, installs)
                alias_file.write_text("".join(
                    f"alias {alias} {name.replace('-', '_')}\n"
                    for name, alias in LAPTOP_ALIASES.items()) +
                    "alias pci:v00008086d000056A0sv*sd*bc03sc*i* i915\n")
                with self.assertRaisesRegex(ValueError, "only the verified Broadwell"):
                    check(root, installs)

    def test_broadwell_modules_are_modular_and_explicitly_packaged(self):
        config = (REPO / "kernel/gki.config").read_text()
        paths = (REPO / "kernel/laptop-modules.list").read_text().splitlines()
        installs = (REPO / "android/vendor_dlkm/install.list").read_text()
        for option in ("DRM_I915", "INTEL_GTT"):
            self.assertIn(f"CONFIG_{option}=m\n", config)
        for path in ("drivers/gpu/drm/i915/i915.ko", "drivers/char/agp/intel-gtt.ko"):
            self.assertIn(path, paths)
            self.assertIn(f"gki/{Path(path).name}", installs)
        module_patch = (REPO / "android/vendor_dlkm/modules.patch").read_text()
        self.assertIn("+alias pci:v00008086d00001616sv*sd*bc03sc*i* i915\n", module_patch)
        self.assertEqual(
            [line for line in module_patch.splitlines()
             if line.startswith("+alias ") and line.endswith(" i915")],
            ["+alias pci:v00008086d00001616sv*sd*bc03sc*i* i915"],
        )

    def test_ar9565_uses_upstream_modules_without_replacing_google_wireless_helpers(self):
        config = (REPO / "kernel/gki.config").read_text()
        paths = (REPO / "kernel/laptop-modules.list").read_text().splitlines()
        installs = (REPO / "android/vendor_dlkm/install.list").read_text()
        for option in ("ATH_COMMON", "ATH9K", "ATH9K_HW", "ATH9K_COMMON"):
            self.assertIn(f"CONFIG_{option}=m\n", config)
        for path in ("drivers/net/wireless/ath/ath.ko",
                     "drivers/net/wireless/ath/ath9k/ath9k_hw.ko",
                     "drivers/net/wireless/ath/ath9k/ath9k_common.ko",
                     "drivers/net/wireless/ath/ath9k/ath9k.ko"):
            self.assertIn(path, paths)
            self.assertIn(f"gki/{Path(path).name}", installs)
        for name in ("cfg80211.ko", "mac80211.ko"):
            self.assertNotIn(f"gki/{name}", installs)
            self.assertFalse(any(Path(path).name == name for path in paths))
        module_patch = (REPO / "android/vendor_dlkm/modules.patch").read_text()
        alias = "pci:v0000168Cd00000036sv*sd*bc*sc*i*"
        self.assertEqual(LAPTOP_ALIASES["ath9k"], alias)
        self.assertIn(f"+alias {alias} ath9k\n", module_patch)

    def test_sound_module_paths_keep_traversal_and_root_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            build = work / "build"
            build.mkdir()
            (build / ".config").write_text('CONFIG_MODULE_SIG_HASH="sha256"\n')
            listing = work / "modules.list"
            for path in ("sound/../outside.ko", "/sound/absolute.ko",
                         "other/module.ko", "sound/soc/amd/not-a-module"):
                with self.subTest(path=path):
                    listing.write_text(path + "\n")
                    result = subprocess.run(
                        ["bash", str(REPO / "scripts/laptop-modules.sh"), str(build),
                         str(work), str(listing), str(work), str(work / "output")],
                        capture_output=True, text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(f"Invalid laptop module path: {path}", result.stderr)


if __name__ == "__main__":
    unittest.main()
