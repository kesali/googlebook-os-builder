"""Verify atomic raw/ZIP fetching using only temporary files and file:// URLs."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/fetch.sh"
MEMBER = "android-desktop_signed_recovery_image.bin"


class FetchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.destination = self.root / "published/source.bin"
        self.data = b"unchanged upstream bytes\n"
        self.digest = hashlib.sha256(self.data).hexdigest()

    def fetch(self, *extra, digest=None):
        return subprocess.run(
            ["bash", str(SCRIPT), self.source.as_uri(), digest or self.digest,
             str(self.destination), *extra], capture_output=True, text=True)

    def assert_no_scratch(self):
        self.assertEqual(list(self.destination.parent.glob("*.partial.*")), [])

    def test_raw_fetch_remains_verified_and_repeat_preserves_timestamp(self):
        self.source.write_bytes(self.data)
        result = self.fetch()
        self.assertEqual(result.returncode, 0, result.stderr)
        before = self.destination.stat().st_mtime_ns
        self.source.unlink()
        self.assertEqual(self.fetch().returncode, 0)
        self.assertEqual(self.destination.stat().st_mtime_ns, before)
        self.assert_no_scratch()

    def test_zip_verifies_published_member_not_transport_bytes(self):
        with zipfile.ZipFile(self.source, "w") as archive:
            archive.writestr(MEMBER, self.data)
        result = self.fetch(MEMBER)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.destination.read_bytes(), self.data)
        self.assert_no_scratch()

    def test_checksum_failure_preserves_existing_file(self):
        self.destination.parent.mkdir()
        self.destination.write_bytes(b"old file")
        with zipfile.ZipFile(self.source, "w") as archive:
            archive.writestr(MEMBER, b"wrong bytes")
        result = self.fetch(MEMBER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.destination.read_bytes(), b"old file")
        self.assert_no_scratch()

    def test_missing_zip_member_is_not_published(self):
        with zipfile.ZipFile(self.source, "w") as archive:
            archive.writestr("other", self.data)
        result = self.fetch(MEMBER)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())
        self.assert_no_scratch()

    def test_missing_download_is_not_published(self):
        result = self.fetch()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())
        self.assert_no_scratch()


if __name__ == "__main__":
    unittest.main()
