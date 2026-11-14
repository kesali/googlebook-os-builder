"""Exercise runtime graphics selection with fake sysfs; never touch real devices."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "android/system_ext/graphics-select.sh"


class GraphicsSelectorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.sys = self.work / "sys"
        (self.sys / "class/drm").mkdir(parents=True)
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.selected = self.work / "selected"
        setprop = self.bin / "setprop"
        setprop.write_text(
            "#!/bin/sh\n"
            "test \"$1\" = sys.gbos_builder.graphics\n"
            "printf '%s\\n' \"$2\" > \"$SELECTED_PROFILE\"\n"
        )
        setprop.chmod(0o755)

    def add_gpu(self, card, driver, device_id=None, boot_vga=None):
        device = self.sys / f"class/drm/{card}/device"
        device.mkdir(parents=True)
        (self.work / "drivers").mkdir(exist_ok=True)
        (device / "driver").symlink_to(self.work / "drivers" / driver)
        if device_id is not None:
            (device / "device").write_text(device_id + "\n")
        if boot_vga is not None:
            (device / "boot_vga").write_text(boot_vga + "\n")

    def select(self):
        environment = dict(
            os.environ,
            PATH=f"{self.bin}:{os.environ['PATH']}",
            SELECTED_PROFILE=str(self.selected),
        )
        return subprocess.run(
            ["sh", str(SELECTOR), str(self.sys)],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_maps_amdgpu_to_the_amd_profile(self):
        self.add_gpu("card0", "amdgpu", boot_vga="1")

        self.select()

        self.assertEqual(self.selected.read_text(), "amd\n")

    def test_maps_known_broadwell_to_hasvk(self):
        self.add_gpu("card0", "i915", "0x1616", "1")

        self.select()

        self.assertEqual(self.selected.read_text(), "intel-hasvk\n")

    def test_maps_newer_i915_and_xe_to_anv(self):
        self.add_gpu("card0", "i915", "0x9a49", "1")
        self.select()
        self.assertEqual(self.selected.read_text(), "intel-anv\n")

        device = self.sys / "class/drm/card0/device"
        (device / "driver").unlink()
        (device / "driver").symlink_to(self.work / "drivers/xe")
        (device / "device").write_text("0x7d55\n")
        self.select()
        self.assertEqual(self.selected.read_text(), "intel-anv\n")

    def test_keeps_unknown_drivers_on_softpipe(self):
        self.add_gpu("card0", "virtio_gpu", boot_vga="1")

        self.select()

        self.assertEqual(self.selected.read_text(), "softpipe\n")

    def test_selects_boot_vga_when_multiple_supported_gpus_are_bound(self):
        self.add_gpu("card0", "amdgpu", boot_vga="0")
        self.add_gpu("card1", "i915", "0x9a49", boot_vga="1")

        self.select()

        self.assertEqual(self.selected.read_text(), "intel-anv\n")

    def test_selector_can_set_only_its_private_property(self):
        policy = (ROOT / "android/system/bootlog-policy.patch").read_text()
        contexts = (ROOT / "android/system/bootlog-property-contexts.patch").read_text()

        self.assertIn(
            "+(allow gbos_builder_graphics_select gbos_builder_graphics_prop "
            "(property_service (set)))",
            policy,
        )
        self.assertIn(
            "+(allow init gbos_builder_graphics_select "
            "(process (transition siginh rlimitinh)))",
            policy,
        )
        self.assertIn(
            "+sys.gbos_builder.graphics "
            "u:object_r:gbos_builder_graphics_prop:s0 exact string",
            contexts,
        )
        self.assertNotIn(
            "+(allow gbos_builder_hardware_diag system_prop (property_service (set)))",
            policy,
        )
        self.assertNotIn(
            "+(allow gbos_builder_hardware_diag gbos_builder_graphics_prop "
            "(property_service (set)))",
            policy,
        )


if __name__ == "__main__":
    unittest.main()
