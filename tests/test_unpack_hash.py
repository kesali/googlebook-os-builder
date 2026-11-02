"""Verify that unpack rejects an unexpected recovery image before touching its output."""

from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
UNPACK_SCRIPT = REPO / "scripts/unpack.sh"


class RecoveryImageHashTests(unittest.TestCase):
    def test_hash_mismatch_preserves_existing_extracted_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recovery = root / "recovery.bin"
            recovery.write_bytes(b"not the pinned image")
            output = root / "google"
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("existing output")

            result = subprocess.run(
                ["bash", str(UNPACK_SCRIPT), str(recovery), str(output), "0" * 64],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA-256 mismatch", result.stderr)
            self.assertEqual(sentinel.read_text(), "existing output")

    def test_invalid_expected_hash_is_rejected_before_reading_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run(
                ["bash", str(UNPACK_SCRIPT), str(root / "missing.bin"), str(root / "google"), "invalid"],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exactly 64 hexadecimal characters", result.stderr)
            self.assertFalse((root / "google").exists())


if __name__ == "__main__":
    unittest.main()
