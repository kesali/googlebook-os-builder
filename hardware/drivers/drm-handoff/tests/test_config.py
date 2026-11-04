"""Check native-only display configuration without building or touching hardware."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))
import hardware_recipes


class NativeDisplayConfigTests(unittest.TestCase):
    def test_native_graphics_without_firmware_framebuffer_or_screen_log(self):
        config = hardware_recipes.expand(ROOT / "kernel/gki.config").splitlines()
        for symbol in ("SYSFB", "SYSFB_SIMPLEFB", "DRM_SIMPLEDRM", "DRM_CLIENT_LOG"):
            with self.subTest(symbol=symbol):
                self.assertIn(f"# CONFIG_{symbol} is not set", config)
                self.assertNotIn(f"CONFIG_{symbol}=y", config)
                self.assertNotIn(f"CONFIG_{symbol}=m", config)


if __name__ == "__main__":
    unittest.main()
