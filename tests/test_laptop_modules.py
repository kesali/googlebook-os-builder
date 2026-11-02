"""Dependency metadata checks use fake module graphs."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from laptop_module_check import dependency_closure


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


if __name__ == "__main__":
    unittest.main()
