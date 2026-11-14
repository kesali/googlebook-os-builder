"""Verify atomic raw/ZIP fetching using only temporary files and file:// URLs."""

import hashlib
import os
from pathlib import Path
import shlex
import shutil
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

    def fetch(self, *extra, digest=None, env=None):
        return subprocess.run(
            ["bash", str(SCRIPT), self.source.as_uri(), digest or self.digest,
             str(self.destination), *extra], capture_output=True, text=True, env=env)

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

    def test_interrupted_download_resumes_and_publishes_verified_bytes(self):
        self.source.write_bytes(self.data)
        curl = shutil.which("curl")
        self.assertIsNotNone(curl)
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        marker = self.root / "interrupted"
        wrapper = fake_bin / "curl"
        wrapper.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"if [ ! -e {shlex.quote(str(marker))} ]; then\n"
            "    output=\n"
            "    while [ \"$#\" -gt 0 ]; do\n"
            "        if [ \"$1\" = --output ]; then output=$2; break; fi\n"
            "        shift\n"
            "    done\n"
            "    printf 'unchanged ' > \"$output\"\n"
            f"    touch {shlex.quote(str(marker))}\n"
            "    exit 18\n"
            "fi\n"
            f"exec {shlex.quote(curl)} \"$@\"\n"
        )
        wrapper.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

        interrupted = self.fetch(env=env)
        self.assertNotEqual(interrupted.returncode, 0)
        self.assertFalse(self.destination.exists())
        partials = list(self.destination.parent.glob("*.partial.*"))
        self.assertEqual(len(partials), 1)
        self.assertEqual((partials[0] / "source").read_bytes(), b"unchanged ")

        resumed = self.fetch(env=env)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(self.destination.read_bytes(), self.data)
        self.assert_no_scratch()


if __name__ == "__main__":
    unittest.main()
