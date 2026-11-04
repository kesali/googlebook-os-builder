"""The declared Android changes and the scripts that apply and check them."""

from pathlib import Path
import unittest
import sys


REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand


def entries(path):
    return [line.split() for line in expand(path).splitlines()
            if line.strip() and not line.startswith("#")]


class ChangeDataTests(unittest.TestCase):
    def test_first_stage_modules_are_loaded_in_install_order(self):
        changes = REPO / "android/module_ramdisk"
        patch = (REPO / "hardware/drivers/qemu-virtio/module_ramdisk/modules.patch").read_text()
        # Android reads a trailing space in modules.dep as an empty dependency.
        self.assertNotRegex(patch, r"(?m)[ \t]$")
        installed = [Path(entry[0]).name for entry in entries(changes / "install.list")]
        load = patch.split("+++ b/lib/modules/modules.load\n", 1)[1]
        added = [line[1:] for line in load.splitlines() if line.startswith("+")]
        self.assertEqual(added, installed)


if __name__ == "__main__":
    unittest.main()
