"""Check this recipe using local fixtures, never real hardware."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests"))


class VendoredEmulatorTests(unittest.TestCase):
    def make(self, *arguments, extra_rules=None):
        command = ["make", "--no-print-directory", "-f", str(ROOT / "Makefile")]
        if extra_rules is not None:
            command.extend(["-f", "-"])
        return subprocess.run(
            [*command, *arguments], cwd=ROOT, input=extra_rules,
            capture_output=True, text=True,
        )

    def test_vendored_patch_matches_working_baseline(self):
        patch = ROOT / "hardware/drivers/cpu-vex/vex-emulate.patch"
        self.assertEqual(
            hashlib.sha256(patch.read_bytes()).hexdigest(),
            "d8decdcffc7a87aea0386ec3ca8476e607f5a26f0ef127e4f051f65ab84e8e0f",
        )
        self.assertNotIn("$(EMU_URL)", (ROOT / "Makefile").read_text())
        self.assertNotIn("\nEMU_URL :=", (ROOT / "sources.mk").read_text())

    def test_new_patch_timestamp_does_not_replace_existing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            ready = source / ".ready"
            ready.touch()
            os.utime(ready, (1, 1))
            builder_ready = source / "builder-ready"
            builder_ready.touch()
            result = self.make(
                "-n", "sources", f"KERNEL_SRC={source}", "KERNEL_PATCHES=",
                f"BUILD_READY={builder_ready}",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("kernel-source.sh", result.stdout)
            self.assertNotIn("fetch.sh", result.stdout)

    def test_emulator_content_changes_select_a_new_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            patch = Path(directory) / "emulator.patch"
            caches = []
            for contents in (b"original patch\n", b"modified patch\n"):
                patch.write_bytes(contents)
                result = self.make(
                    "inspect-emulator", f"EMU_PATCH={patch}",
                    extra_rules=".PHONY: inspect-emulator\n"
                    "inspect-emulator:\n\t@printf '%s\\n' '$(KERNEL_CACHE)'\n",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(
                    result.stdout.strip().endswith(hashlib.sha256(contents).hexdigest()),
                    result.stdout,
                )
                caches.append(result.stdout.strip())
            self.assertNotEqual(caches[0], caches[1])


if __name__ == "__main__":
    unittest.main()
