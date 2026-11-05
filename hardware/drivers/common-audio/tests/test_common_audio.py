"""Check audio firmware declarations and synthetic extraction; never touch audio devices."""

import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand

RECIPE = Path(__file__).resolve().parents[1]
FILES = ("ctefx.bin", "LICENSES/LICENCE.ca0132")


class CommonAudioTests(unittest.TestCase):
    def test_selected_firmware_is_installed_without_replacing_drivers_or_routes(self):
        self.assertIn("common-audio\n", (REPO / "hardware/drivers.list").read_text())
        manifest = expand(REPO / "kernel/firmware.list").splitlines()
        installs = expand(REPO / "android/vendor/install.list").splitlines()
        for name in FILES:
            self.assertIn(name, manifest)
            self.assertIn(f"firmware/{name} 0644 0:0 vendor_firmware_file firmware/{name}",
                          installs)
        self.assertFalse((RECIPE / "gki.config").exists())
        self.assertFalse((RECIPE / "modules.list").exists())
        self.assertEqual(len((RECIPE / "vendor.install").read_text().splitlines()), 2)

    def test_extracts_only_declared_runtime_firmware_and_preserves_repeat_timestamps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "firmware.tar"
            with tarfile.open(archive, "w") as stream:
                for name in FILES:
                    data = name.encode()
                    info = tarfile.TarInfo(f"linux-firmware-test/{name}")
                    info.size = len(data)
                    stream.addfile(info, io.BytesIO(data))
            output = root / "output"
            command = ["bash", str(REPO / "scripts/firmware.sh"), str(archive), "test",
                       str(RECIPE / "firmware.list"), str(output)]
            subprocess.run(command, capture_output=True, text=True, check=True)
            before = {path: path.stat().st_mtime_ns for path in output.rglob("*")
                      if path.is_file()}
            for name in FILES:
                self.assertEqual((output / name).read_bytes(), name.encode())
            subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertEqual({path: path.stat().st_mtime_ns for path in before}, before)
            listing = root / "invalid.list"
            for name in ("../ctefx.bin", "/ctefx.bin", "ctefx-update.bin",
                         "LICENSES/../ctefx.bin"):
                listing.write_text(name + "\n")
                result = subprocess.run(command[:4] + [str(listing), str(output)],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Invalid runtime firmware path", result.stderr)


if __name__ == "__main__":
    unittest.main()
