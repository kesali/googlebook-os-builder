"""Check shared network declarations and firmware extraction using synthetic files only."""

import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand
from laptop_module_check import check_module_aliases

RECIPE = Path(__file__).resolve().parents[1]


def entries(path):
    return [line for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")]


class CommonNetworkTests(unittest.TestCase):
    def test_selected_recipe_wires_modules_firmware_and_metadata(self):
        self.assertIn("common-network", entries(REPO / "hardware/drivers.list"))
        for path, fragment in (
                ("kernel/gki.config", "gki.config"),
                ("kernel/laptop-modules.list", "modules.list"),
                ("kernel/firmware.list", "firmware.list"),
                ("android/vendor/install.list", "vendor.install"),
                ("android/vendor_dlkm/install.list", "vendor_dlkm.install"),
                ("android/vendor_dlkm/patches.list", "vendor_dlkm.patches")):
            self.assertIn(f"# recipe: common-network/{fragment}", (REPO / path).read_text())

    def test_new_modules_have_installs_and_dependency_records_without_google_replacements(self):
        sources = entries(RECIPE / "modules.list")
        installed = entries(RECIPE / "vendor_dlkm.install")
        self.assertEqual(len(sources), 23)
        self.assertEqual({Path(path).name for path in sources},
                         {Path(line.split()[0]).name for line in installed})
        metadata = (RECIPE / "vendor_dlkm/modules.patch").read_text()
        for path in sources:
            name = Path(path).name
            self.assertIn(f"+/vendor/lib/modules/{name}:", metadata)
            self.assertIn(f"gki/{name}", expand(REPO / "android/vendor_dlkm/install.list"))
        for name in ("iwlwifi", "iwlmvm", "iwlmld", "cfg80211", "mac80211",
                     "e1000e", "igc", "r8169"):
            self.assertNotIn(f"gki/{name}.ko", "\n".join(installed))

    def test_common_pcie_adapters_have_hotplug_aliases(self):
        metadata = (RECIPE / "vendor_dlkm/modules.patch").read_text()
        for device, module in (
                ("1533", "igb"), ("1539", "igb"),
                ("D723", "rtw88_8723de"), ("B821", "rtw88_8821ce"),
                ("C821", "rtw88_8821ce"), ("B822", "rtw88_8822be"),
                ("C822", "rtw88_8822ce"), ("C82F", "rtw88_8822ce"),
                ("B851", "rtw89_8851be"), ("8852", "rtw89_8852ae"),
                ("A85A", "rtw89_8852ae"), ("B852", "rtw89_8852be"),
                ("B85B", "rtw89_8852be"), ("C852", "rtw89_8852ce")):
            vendor = "8086" if module == "igb" else "10EC"
            self.assertIn(f"+alias pci:v0000{vendor}d0000{device}sv*sd*bc*sc*i* {module}\n",
                          metadata)

    def test_metadata_patch_coexists_with_existing_laptop_additions_without_fuzz(self):
        originals = {
            "modules.dep": (
                "/vendor/lib/modules/arc4.ko: /system/lib/modules/libarc4.ko\n"
                "/system/lib/modules/rust_binder.ko:\n"
                "/vendor/lib/modules/intel_telemetry_debugfs.ko: /vendor/lib/modules/intel_pmc_bxt.ko /vendor/lib/modules/mfd-core.ko /vendor/lib/modules/intel_telemetry_core.ko\n"
                "/vendor/lib/modules/igc.ko: /system/lib/modules/ptp.ko /system/lib/modules/pps_core.ko\n"
                "/vendor/lib/modules/snd-soc-sst-cht-bsw-rt5645.ko: /vendor/lib/modules/snd-soc-rt5645.ko /vendor/lib/modules/snd-soc-rl6231.ko\n"
                "/vendor/lib/modules/snd-sof-pci-intel-tng.ko: /vendor/lib/modules/snd-sof-intel-atom.ko /vendor/lib/modules/snd-sof-xtensa-dsp.ko /vendor/lib/modules/snd-sof-pci.ko /vendor/lib/modules/snd-sof.ko /vendor/lib/modules/snd-sof-utils.ko\n"),
            "modules.alias": (
                "# Aliases extracted from modules themselves.\n"
                "alias ecb(arc4) arc4\n"
                "alias crypto-ecb(arc4) arc4\n"
                "alias pci:v00008086d000015FDsv*sd*bc*sc*i* igc\n"
                "alias platform:cht-bsw-rt5645 snd_soc_sst_cht_bsw_rt5645\n"
                "alias pci:v00008086d0000119Asv*sd*bc*sc*i* snd_sof_pci_intel_tng\n"),
        }
        laptop = (REPO / "hardware/drivers/laptop-modules/vendor_dlkm/modules.patch").read_text()
        laptop = laptop.split("--- a/lib/modules/modules.blocklist\n")[0]
        common = (RECIPE / "vendor_dlkm/modules.patch").read_text()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = root / "lib/modules"
            modules.mkdir(parents=True)
            for name, content in originals.items():
                (modules / name).write_text(content)
            for metadata in (laptop, common):
                result = subprocess.run(
                    ["patch", "--batch", "--fuzz=0", "-p1", "-d", str(root)],
                    input=metadata, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name, content in originals.items():
                final = (modules / name).read_text()
                self.assertIn(content, final)
                for metadata in (laptop, common):
                    section = metadata.split(f"+++ b/lib/modules/{name}\n")[1].split("--- a/")[0]
                    for line in section.splitlines():
                        if line.startswith("+"):
                            self.assertEqual(final.splitlines().count(line[1:]), 1)

    def test_every_firmware_and_license_has_exactly_one_install(self):
        expected = set(entries(RECIPE / "firmware.list"))
        files = [line.split() for line in entries(RECIPE / "vendor.install")
                 if line.split()[4] != "-"]
        self.assertEqual(len(files), len(expected))
        self.assertEqual({fields[4].removeprefix("firmware/") for fields in files}, expected)
        for destination, mode, owner, context, source in files:
            name = source.removeprefix("firmware/")
            if name.startswith("intel/iwlwifi/"):
                self.assertEqual(destination, "firmware/" + Path(name).name)
            else:
                self.assertEqual(destination, "firmware/" + name)
            self.assertEqual((mode, owner, context), ("0644", "0:0", "vendor_firmware_file"))

    def test_extraction_accepts_new_families_and_unchanged_repeat(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = entries(RECIPE / "firmware.list")
            archive = root / "firmware.tar.xz"
            with tarfile.open(archive, "w:xz") as stream:
                for name in paths:
                    data = name.encode()
                    info = tarfile.TarInfo("linux-firmware-test/" + name)
                    info.size = len(data)
                    stream.addfile(info, io.BytesIO(data))
            listing = root / "firmware.list"
            listing.write_text("\n".join(paths) + "\n")
            output = root / "output"
            command = ["bash", str(REPO / "scripts/firmware.sh"), str(archive),
                       "test", str(listing), str(output)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = {path: path.stat().st_mtime_ns for path in output.rglob("*") if path.is_file()}
            for name in paths:
                self.assertEqual((output / name).read_bytes(), name.encode())
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual({path: path.stat().st_mtime_ns for path in before}, before)

    def test_extraction_still_rejects_traversal_and_non_runtime_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "empty.tar"
            archive.touch()
            listing = root / "firmware.list"
            for name in ("rtw88/../../secret.bin", "/rtw89/firmware.bin",
                         "intel/iwlwifi/update.sh", "rtl_nic/flash.sh"):
                listing.write_text(name + "\n")
                result = subprocess.run(
                    ["bash", str(REPO / "scripts/firmware.sh"), str(archive), "test",
                     str(listing), str(root / "output")], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Invalid runtime firmware path", result.stderr)

    def test_compiled_alias_check_accepts_multiple_pci_ids_and_rejects_unknown_or_missing(self):
        module = Path("rtw88_8821ce.ko")
        aliases = ("pci:first", "pci:second")
        def modinfo(command, **kwargs):
            return "rtw88_8821ce\n" if command[2] == "name" else "\n".join(aliases) + "\n"
        with patch("laptop_module_check.subprocess.check_output", side_effect=modinfo):
            check_module_aliases(module, [f"alias {alias} rtw88_8821ce" for alias in aliases],
                                 require_all=True)
            for declared in ([], ["alias pci:wrong rtw88_8821ce"],
                             ["alias pci:first rtw88_8821ce"]):
                with self.assertRaises(ValueError):
                    check_module_aliases(module, declared, require_all=True)
            check_module_aliases(module, ["alias pci:first rtw88_8821ce"])
            check_module_aliases(module, [])
        with patch("laptop_module_check.subprocess.check_output",
                   side_effect=["rtw88_core\n", ""]):
            check_module_aliases(Path("rtw88_core.ko"), [])


if __name__ == "__main__":
    unittest.main()
