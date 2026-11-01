"""Allocator ABI checks use fake symbol sets, never Android images or devices."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from minigbm_abi import missing_symbols


class MinigbmAbiTests(unittest.TestCase):
    def test_used_platform_symbols_must_remain(self):
        self.assertEqual(missing_symbols({"allocate", "map"}, {"allocate"}, {"map"}), ["map"])

    def test_unused_private_exports_do_not_define_client_abi(self):
        self.assertEqual(missing_symbols({"allocate", "unused"}, {"allocate"}, {"allocate"}), [])

    def test_imports_from_other_libraries_are_not_required(self):
        self.assertEqual(missing_symbols({"allocate"}, {"allocate"}, {"allocate", "malloc"}), [])

    def test_platform_and_ndk_cxx_names_are_not_interchangeable(self):
        self.assertEqual(missing_symbols({"std::__1"}, {"std::__ndk1"}, {"std::__1"}), ["std::__1"])


if __name__ == "__main__":
    unittest.main()
