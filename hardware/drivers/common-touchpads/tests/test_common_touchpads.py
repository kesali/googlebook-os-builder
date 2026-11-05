"""Check touchpad packaging with fake modules and text fixtures; never touch devices."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand, patches
from laptop_module_check import check

RECIPE = Path(__file__).resolve().parents[1]
ALIASES = {
    "pinctrl-lynxpoint": ("acpi*:INT33C7:*", "acpi*:INT3437:*", "platform:lp_gpio"),
    "rmi_smbus": ("i2c:rmi4_smbus",),
}
DEPENDENCIES = {"pinctrl-lynxpoint": "pinctrl-intel", "rmi_smbus": "rmi_core"}


class CommonTouchpadTests(unittest.TestCase):
    def test_selected_recipe_wires_config_modules_and_metadata(self):
        self.assertIn("common-touchpads\n", (REPO / "hardware/drivers.list").read_text())
        for surface, fragment in (
                ("kernel/gki.config", "gki.config"),
                ("kernel/laptop-modules.list", "modules.list"),
                ("android/vendor_dlkm/install.list", "vendor_dlkm.install"),
                ("android/vendor_dlkm/patches.list", "vendor_dlkm.patches")):
            self.assertIn(f"# recipe: common-touchpads/{fragment}\n",
                          (REPO / surface).read_text())
        config = expand(REPO / "kernel/gki.config")
        for option in ("PINCTRL_LYNXPOINT", "RMI4_CORE", "RMI4_SMB"):
            self.assertIn(f"CONFIG_{option}=m\n", config)

    def test_only_missing_modules_are_published_without_changing_ps2_defaults(self):
        source = (RECIPE / "modules.list").read_text().splitlines()
        self.assertEqual(source, ["drivers/pinctrl/intel/pinctrl-lynxpoint.ko",
                                  "drivers/input/rmi4/rmi_smbus.ko"])
        installs = (RECIPE / "vendor_dlkm.install").read_text().splitlines()
        self.assertEqual(installs, [
            f"lib/modules/{name}.ko 0644 0:0 vendor_kernel_modules gki/{name}.ko"
            for name in ALIASES
        ])
        for name in ALIASES:
            self.assertIn(f"gki/{name}.ko", expand(REPO / "android/vendor_dlkm/install.list"))
        config = (RECIPE / "gki.config").read_text()
        self.assertNotIn("CONFIG_MOUSE_", config)
        metadata = (RECIPE / "vendor_dlkm/modules.patch").read_text()
        self.assertNotIn("modules.options", metadata)
        self.assertNotIn("modules.load", metadata)
        self.assertNotIn("modules.softdep", metadata)
        for name in ("elan_i2c", "hid-rmi", "rmi_core", "pinctrl-intel", "i2c-i801"):
            self.assertNotIn(f"gki/{name}.ko", "\n".join(installs))

    def test_metadata_declares_native_aliases_and_stock_helpers(self):
        metadata = (RECIPE / "vendor_dlkm/modules.patch").read_text()
        for name, aliases in ALIASES.items():
            dependency = DEPENDENCIES[name]
            self.assertIn(f"+/vendor/lib/modules/{name}.ko: "
                          f"/vendor/lib/modules/{dependency}.ko\n", metadata)
            for alias in aliases:
                self.assertIn(f"+alias {alias} {name.replace('-', '_')}\n", metadata)

    def test_all_selected_module_metadata_patches_coexist_without_fuzz(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = root / "lib/modules"
            shutil.copytree(RECIPE / "tests/fixtures", modules)
            for source in patches(REPO / "android/vendor_dlkm"):
                metadata = source.read_text().split("--- a/lib/modules/modules.blocklist\n")[0]
                result = subprocess.run(
                    ["patch", "--batch", "--fuzz=0", "-p1", "-d", str(root)],
                    input=metadata, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for name in ("modules.dep", "modules.alias"):
                    section = metadata.split(f"+++ b/lib/modules/{name}\n")[1].split("--- a/")[0]
                    final = (modules / name).read_text().splitlines()
                    for line in section.splitlines():
                        if line.startswith("+"):
                            self.assertEqual(final.count(line[1:]), 1)
            for name in ("modules.dep", "modules.alias"):
                final = (modules / name).read_text().splitlines()
                for line in (RECIPE / "tests/fixtures" / name).read_text().splitlines():
                    self.assertEqual(final.count(line), 1)

    def test_module_checker_requires_complete_aliases_and_stock_dependency_closures(self):
        def modinfo(arguments, text):
            name = Path(arguments[-1]).stem
            field = arguments[2]
            return {
                "name": name.replace("-", "_"),
                "alias": "\n".join(ALIASES[name]),
                "depends": DEPENDENCIES[name],
                "signer": "test-key",
            }[field] + "\n"

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = root / "lib/modules"
            modules.mkdir(parents=True)
            installs = root / "install.list"
            installs.write_text((RECIPE / "vendor_dlkm.install").read_text())
            dependencies = "".join(
                f"/vendor/lib/modules/{name}.ko: /vendor/lib/modules/{dependency}.ko\n"
                for name, dependency in DEPENDENCIES.items())
            dependencies += "".join(
                f"/vendor/lib/modules/{name}.ko:\n" for name in DEPENDENCIES.values())
            (modules / "modules.dep").write_text(dependencies)
            aliases = [
                f"alias {alias} {name.replace('-', '_')}\n"
                for name, values in ALIASES.items() for alias in values
            ]
            alias_file = modules / "modules.alias"
            alias_file.write_text("".join(aliases))
            with patch("laptop_module_check.LAPTOP_ALIASES", {}), patch(
                    "laptop_module_check.subprocess.check_output", side_effect=modinfo):
                check(root, installs)
                for missing in aliases:
                    alias_file.write_text("".join(line for line in aliases if line != missing))
                    with self.assertRaisesRegex(ValueError, "hotplug aliases"):
                        check(root, installs)
                alias_file.write_text("".join(aliases))
                (modules / "modules.dep").write_text(dependencies.replace(
                    "/vendor/lib/modules/rmi_smbus.ko: /vendor/lib/modules/rmi_core.ko",
                    "/vendor/lib/modules/rmi_smbus.ko:"))
                with self.assertRaisesRegex(ValueError, "compiled dependencies"):
                    check(root, installs)


if __name__ == "__main__":
    unittest.main()
