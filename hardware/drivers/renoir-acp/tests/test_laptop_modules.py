"""Dependency metadata checks use fake module graphs."""

from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand


class LaptopModuleTests(unittest.TestCase):
    def test_microphone_modules_are_modular_and_installed_without_replacing_dmic(self):
        config = expand(REPO / "kernel/gki.config")
        for option in ("SND_SOC_AMD_RENOIR", "SND_SOC_AMD_RENOIR_MACH",
                       "SND_AMD_ACP_CONFIG", "SND_SOC_DMIC"):
            self.assertIn(f"CONFIG_{option}=m\n", config)
        paths = {line for line in expand(REPO / "kernel/laptop-modules.list").splitlines()
                 if line and not line.startswith("#")}
        installs = [line.split() for line in
                    expand(REPO / "android/vendor_dlkm/install.list").splitlines()
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


if __name__ == "__main__":
    unittest.main()
