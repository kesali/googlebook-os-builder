"""Dependency metadata checks use fake module graphs."""

from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand


class LaptopModuleTests(unittest.TestCase):
    def test_broadwell_modules_are_modular_and_explicitly_packaged(self):
        config = expand(REPO / "kernel/gki.config")
        paths = expand(REPO / "kernel/laptop-modules.list").splitlines()
        installs = expand(REPO / "android/vendor_dlkm/install.list")
        for option in ("DRM_I915", "INTEL_GTT"):
            self.assertIn(f"CONFIG_{option}=m\n", config)
        for path in ("drivers/gpu/drm/i915/i915.ko", "drivers/char/agp/intel-gtt.ko"):
            self.assertIn(path, paths)
            self.assertIn(f"gki/{Path(path).name}", installs)
        module_patch = (REPO / "hardware/drivers/laptop-modules/vendor_dlkm/modules.patch").read_text()
        self.assertIn("+alias pci:v00008086d00001616sv*sd*bc03sc*i* i915\n", module_patch)
        self.assertEqual(
            [line for line in module_patch.splitlines()
             if line.startswith("+alias ") and line.endswith(" i915")],
            ["+alias pci:v00008086d00001616sv*sd*bc03sc*i* i915"],
        )


if __name__ == "__main__":
    unittest.main()
