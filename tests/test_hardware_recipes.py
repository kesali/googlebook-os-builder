"""Verify native-format recipe expansion with temporary declarations, never image writes."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import hardware_recipes


class HardwareRecipeTests(unittest.TestCase):
    def test_existing_recipe_surfaces_and_metadata_agree(self):
        hardware_recipes.validate()
        self.assertEqual(hardware_recipes.drivers(), [
            "cpu-vex", "drm-handoff", "amdgpu", "renoir-acp", "i915",
            "amd-i2c-hid", "mt7922", "elantech-ps2", "ar9565",
            "laptop-modules", "qemu-virtio",
        ])
        self.assertEqual(len(hardware_recipes.aliases()), 8)
        self.assertEqual(hardware_recipes.aliases()["psmouse"], "serio:ty01pr*id*ex*")
        self.assertEqual(hardware_recipes.aliases()["ath9k"],
                         "pci:v0000168Cd00000036sv*sd*bc*sc*i*")

    def test_expansion_preserves_order_and_leaves_no_build_directives(self):
        text = hardware_recipes.expand(REPO / "kernel/laptop-modules.list")
        self.assertLess(text.index("psmouse.ko"), text.index("mt76.ko"))
        self.assertLess(text.index("mt7921e.ko"), text.index("ath.ko"))
        self.assertNotIn("# recipe:", text)
        self.assertEqual(text.count("drivers/input/mouse/psmouse.ko\n"), 1)

    def test_unknown_malformed_duplicate_and_traversal_includes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config"
            for text in ("# recipe: unknown/gki.config\n",
                         "# recipe:ar9565/gki.config\n",
                         "# recipe: ../gki.config\n",
                         "# recipe: ar9565/../../private\n",
                         "# recipe: ar9565/gki.config\n# recipe: ar9565/gki.config\n"):
                with self.subTest(text=text):
                    path.write_text(text)
                    with self.assertRaises(ValueError):
                        hardware_recipes.expand(path)

    def test_nested_or_unterminated_fragments_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            driver = root / "drivers/ar9565"
            driver.mkdir(parents=True)
            source = root / "input"
            source.write_text("# recipe: ar9565/gki.config\n")
            for text in ("# recipe: ar9565/gki.config\n", "CONFIG_ATH9K=m"):
                with self.subTest(text=text):
                    (driver / "gki.config").write_text(text)
                    with patch.object(hardware_recipes, "recipes", return_value={"ar9565": driver}):
                        with self.assertRaisesRegex(ValueError, "Nested or unterminated"):
                            hardware_recipes.expand(source)

    def test_symlinked_fragment_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            driver = root / "drivers/ar9565"
            driver.mkdir(parents=True)
            target = root / "outside"
            target.write_text("CONFIG_ATH9K=m\n")
            (driver / "gki.config").symlink_to(target)
            source = root / "input"
            source.write_text("# recipe: ar9565/gki.config\n")
            with patch.object(hardware_recipes, "recipes", return_value={"ar9565": driver}):
                with self.assertRaisesRegex(ValueError, "symlinked"):
                    hardware_recipes.expand(source)

    def test_driver_selection_rejects_duplicates_and_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            device = Path(temporary)
            (device / "drivers/ar9565").mkdir(parents=True)
            for text in ("../outside\n", "ar9565\nar9565\n", ""):
                with self.subTest(text=text):
                    (device / "drivers.list").write_text(text)
                    with patch.object(hardware_recipes, "HARDWARE", device):
                        with self.assertRaises(ValueError):
                            hardware_recipes.drivers()

    def test_base_without_selected_includes_is_rejected(self):
        path = REPO / "kernel/gki.config"
        original_read = Path.read_text

        def read(instance, *args, **kwargs):
            if instance == path:
                return "CONFIG_SYSTEM_TRUSTED_KEYS=\"google-certs.pem\"\n"
            return original_read(instance, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            with self.assertRaisesRegex(ValueError, "exactly once"):
                hardware_recipes.expand(path)

    def test_patch_manifests_preserve_shared_and_recipe_order(self):
        paths = hardware_recipes.patches(REPO / "android/vendor")
        self.assertEqual([path.name for path in paths], [
            "audio-msi.patch", "audio-policy.patch", "build-prop.patch",
            "camera-msi.patch", "camera-va-driver.patch", "file-contexts.patch",
            "powerhint.patch", "ueventd.patch",
        ])

    def test_recipe_local_assets_are_rebased_without_changing_install_metadata(self):
        text = hardware_recipes.expand(REPO / "android/system_ext/install.list")
        self.assertIn("etc/gbos-builder/graphics-intel.rc 0644 0:0 system_file "
                      "hardware/drivers/i915/system_ext/graphics-intel.rc\n", text)
        self.assertIn("etc/init/zz-gbos-builder.rc", text)

    def test_runtime_firmware_includes_both_gpu_and_wireless_recipes(self):
        text = hardware_recipes.expand(REPO / "kernel/firmware.list")
        self.assertIn("amdgpu/renoir_gpu_info.bin\n", text)
        self.assertIn("amdgpu/green_sardine_vcn.bin\n", text)
        self.assertIn("mediatek/BT_RAM_CODE_MT7922_1_1_hdr.bin\n", text)
        self.assertNotIn("# recipe:", text)


class TemporaryRecipeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.hardware = self.repo / "hardware"
        self.driver = self.hardware / "drivers/example"
        self.driver.mkdir(parents=True)
        self.device = self.hardware / "example-laptop"
        self.device.mkdir()
        (self.hardware / "drivers.list").write_text("example\n")
        (self.hardware / "devices.list").write_text("example-laptop\n")
        self.changes = self.repo / "android/vendor"
        self.changes.mkdir(parents=True)
        for attribute, value in (("REPO", self.repo), ("HARDWARE", self.hardware)):
            patcher = patch.object(hardware_recipes, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_selected_recipes_can_omit_unneeded_native_surfaces(self):
        (self.changes / "install.list").write_text("# shared only\n")
        self.assertEqual(hardware_recipes.expand(self.changes / "install.list"), "# shared only\n")
        (self.driver / "vendor.install").write_text("etc/example/ 0755 0:0 vendor_file -\n")
        with self.assertRaisesRegex(ValueError, "exactly once"):
            hardware_recipes.expand(self.changes / "install.list")
        (self.changes / "install.list").write_text("# recipe: example/vendor.install\n")
        self.assertIn("etc/example/", hardware_recipes.expand(self.changes / "install.list"))

    def test_fragment_cannot_be_used_on_the_wrong_partition_surface(self):
        (self.driver / "gki.config").write_text("CONFIG_EXAMPLE=m\n")
        (self.changes / "install.list").write_text("# recipe: example/gki.config\n")
        with self.assertRaisesRegex(ValueError, "does not belong"):
            hardware_recipes.expand(self.changes / "install.list")

    def test_local_install_asset_rejects_traversal_missing_and_symlinked_parents(self):
        (self.changes / "install.list").write_text("# recipe: example/vendor.install\n")
        target = self.repo / "outside"
        target.mkdir()
        (target / "asset").write_text("private\n")
        (self.driver / "linked").symlink_to(target, target_is_directory=True)
        for source in ("./../outside/asset", "./missing", "./linked/asset"):
            with self.subTest(source=source):
                (self.driver / "vendor.install").write_text(f"etc/asset 0644 0:0 vendor_file {source}\n")
                with self.assertRaises(ValueError):
                    hardware_recipes.expand(self.changes / "install.list")

    def test_device_and_driver_names_must_not_collide(self):
        (self.hardware / "devices.list").write_text("example\n")
        (self.hardware / "example").mkdir()
        with self.assertRaisesRegex(ValueError, "duplicates driver"):
            hardware_recipes.recipes()

    def test_symlinked_recipe_selection_directory_and_aliases_are_rejected(self):
        (self.driver / "aliases").symlink_to(self.repo / "missing")
        with self.assertRaisesRegex(ValueError, "Symlinked"):
            hardware_recipes.aliases()
        (self.hardware / "drivers.list").unlink()
        (self.hardware / "drivers.list").symlink_to(self.hardware / "devices.list")
        with self.assertRaisesRegex(ValueError, "Symlinked"):
            hardware_recipes.drivers()
        (self.hardware / "drivers.list").unlink()
        (self.hardware / "drivers.list").write_text("linked\n")
        (self.hardware / "drivers/linked").symlink_to(self.driver, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            hardware_recipes.drivers()

    def test_patch_manifest_requires_every_local_patch_once(self):
        (self.changes / "a.patch").write_text("patch\n")
        for manifest in ("# omitted\n", "a.patch\na.patch\n"):
            with self.subTest(manifest=manifest):
                (self.changes / "patches.list").write_text(manifest)
                with self.assertRaises(ValueError):
                    hardware_recipes.patches(self.changes)

    def test_selected_patch_fragment_cannot_be_silently_skipped_without_a_manifest(self):
        (self.driver / "vendor.patches").write_text("missing.patch\n")
        with self.assertRaisesRegex(ValueError, "require a patch manifest"):
            hardware_recipes.patches(self.changes)

    def test_dangling_patch_manifest_is_rejected(self):
        (self.changes / "patches.list").symlink_to(self.repo / "missing")
        with self.assertRaisesRegex(ValueError, "Symlinked patch manifest"):
            hardware_recipes.patches(self.changes)

    def test_patch_fallback_keeps_name_order_and_rejects_symlinks(self):
        for name in ("b.patch", "a.patch"):
            (self.changes / name).write_text("patch\n")
        self.assertEqual([path.name for path in hardware_recipes.patches(self.changes)],
                         ["a.patch", "b.patch"])
        (self.changes / "linked.patch").symlink_to(self.changes / "a.patch")
        with self.assertRaisesRegex(ValueError, "symlinked"):
            hardware_recipes.patches(self.changes)

    def test_patch_manifest_rejects_unselected_traversing_and_symlinked_sources(self):
        (self.driver / "vendor").mkdir()
        (self.driver / "vendor/valid.patch").write_text("patch\n")
        (self.driver / "vendor/linked.patch").symlink_to(self.driver / "vendor/valid.patch")
        for source in ("../outside.patch", "vendor/linked.patch", "vendor/missing.patch"):
            with self.subTest(source=source):
                (self.changes / "patches.list").write_text("# recipe: example/vendor.patches\n")
                (self.driver / "vendor.patches").write_text(source + "\n")
                with self.assertRaises(ValueError):
                    hardware_recipes.patches(self.changes)
        (self.changes / "patches.list").write_text("# recipe: unselected/vendor.patches\n")
        with self.assertRaisesRegex(ValueError, "unselected"):
            hardware_recipes.patches(self.changes)

    def test_grouped_patch_fragments_must_each_be_included_once(self):
        for group in ("first", "second"):
            (self.driver / f"{group}.patch").write_text("patch\n")
            (self.driver / f"vendor-{group}.patches").write_text(f"{group}.patch\n")
        (self.changes / "patches.list").write_text("# recipe: example/vendor-first.patches\n")
        with self.assertRaisesRegex(ValueError, "exactly once"):
            hardware_recipes.patches(self.changes)
        (self.changes / "patches.list").write_text(
            "# recipe: example/vendor-second.patches\n# recipe: example/vendor-first.patches\n")
        self.assertEqual([path.name for path in hardware_recipes.patches(self.changes)],
                         ["second.patch", "first.patch"])


if __name__ == "__main__":
    unittest.main()
