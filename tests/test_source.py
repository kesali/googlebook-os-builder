"""Verify that release sources are patched in order without replacing existing trees."""

from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SOURCE_SCRIPT = REPO / "scripts/source.sh"


class SourcePreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        original = self.work / "original.txt"
        original.write_text("original\n")
        self.archive = self.work / "release.tar.gz"
        with tarfile.open(self.archive, "w:gz") as archive:
            archive.add(original, arcname="release/state.txt")
        self.first_patch = self.work / "first.patch"
        self.second_patch = self.work / "second.patch"
        self.first_patch.write_text(self.patch("original", "first"))
        self.second_patch.write_text(self.patch("first", "second"))
        self.destination = self.work / "new-source"

    @staticmethod
    def patch(before, after):
        return f"--- a/state.txt\n+++ b/state.txt\n@@ -1 +1 @@\n-{before}\n+{after}\n"

    def prepare(self, patches=()):
        return subprocess.run(
            ["bash", str(SOURCE_SCRIPT), str(self.archive), str(self.destination),
             *(str(patch) for patch in patches)],
            capture_output=True,
            text=True,
        )

    def test_source_can_be_extracted_without_patches(self):
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "state.txt").read_text(), "original\n")
        self.assertTrue((self.destination / ".ready").is_file())

    def test_all_patches_are_applied_in_order(self):
        result = self.prepare((self.first_patch, self.second_patch))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "state.txt").read_text(), "second\n")
        self.assertTrue((self.destination / ".ready").is_file())
        self.assertEqual(list(self.work.glob("new-source.partial.*")), [])

    def test_failed_patch_does_not_publish_a_source_tree(self):
        self.second_patch.write_text(self.patch("different", "second"))
        result = self.prepare((self.first_patch, self.second_patch))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.work.glob("new-source.partial.*")), [])

    def test_existing_destination_is_not_replaced(self):
        self.destination.mkdir()
        original = self.destination / "owner-edit"
        original.write_text("keep\n")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to replace", result.stderr)
        self.assertEqual(original.read_text(), "keep\n")


if __name__ == "__main__":
    unittest.main()
