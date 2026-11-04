"""Exercise Mesa publication without compiling or downloading its dependencies."""

from pathlib import Path
import unittest
import sys


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))
from hardware_recipes import expand


class MesaPublicationTests(unittest.TestCase):
    def test_va_driver_is_explicitly_enabled_and_packaged_without_replacing_libva(self):
        script = (ROOT / "scripts/mesa.sh").read_text()
        self.assertIn("-Dgallium-drivers=softpipe,zink,iris -Dvulkan-drivers=amd,intel_hasvk", script)
        self.assertIn("-Dgallium-drivers=radeonsi -Dvulkan-drivers=", script)
        self.assertIn("-Dgallium-va=enabled", script)
        self.assertIn("-Dvideo-codecs=jpegdec", script)
        self.assertIn("-Dopengl=false", script)
        self.assertIn("-Dllvm=disabled -Damd-use-llvm=false", script)
        installs = [line.split() for line in
                    expand(ROOT / "android/vendor/install.list").splitlines()
                    if line and not line.startswith("#")]
        self.assertIn(["lib64/radeonsi_drv_video.so", "0644", "0:0",
                       "same_process_hal_file", "mesa/lib64/radeonsi_drv_video.so"], installs)
        self.assertIn(["lib64/libdrm_amdgpu.so", "0644", "0:0",
                       "same_process_hal_file", "mesa/lib64/libdrm_amdgpu.so"], installs)
        self.assertFalse(any(Path(line[0]).name in ("libva.so", "libdrm.so")
                             for line in installs))


if __name__ == "__main__":
    unittest.main()
