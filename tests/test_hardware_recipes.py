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
        self.assertEqual(hardware_recipes.drivers(), ["elantech-ps2", "ar9565"])
        self.assertEqual(hardware_recipes.aliases(),
                         {"psmouse": "serio:ty01pr*id*ex*",
                          "ath9k": "pci:v0000168Cd00000036sv*sd*bc*sc*i*"})

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
                    with patch.object(hardware_recipes, "HARDWARE", root), \
                            patch.object(hardware_recipes, "drivers", return_value=["ar9565"]):
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
            with patch.object(hardware_recipes, "HARDWARE", root), \
                    patch.object(hardware_recipes, "drivers", return_value=["ar9565"]):
                with self.assertRaisesRegex(ValueError, "symlinked"):
                    hardware_recipes.expand(source)

    def test_driver_selection_rejects_duplicates_and_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            device = Path(temporary)
            for text in ("../outside\n", "ar9565\nar9565\n", ""):
                with self.subTest(text=text):
                    (device / "drivers.list").write_text(text)
                    with patch.object(hardware_recipes, "DEVICE", device):
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


if __name__ == "__main__":
    unittest.main()
