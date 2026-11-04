"""Check this recipe using local fixtures, never real hardware."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests"))
from recipe_support import inspect_kernel_recipes, recipe_patch


class RenoirCapturePatchTests(unittest.TestCase):
    def test_patch_accepts_android_buffers_and_preserves_legacy_limits(self):
        original = (
            "#define CAPTURE_MIN_NUM_PERIODS     4\n"
            "#define CAPTURE_MAX_NUM_PERIODS     4\n"
            "#define CAPTURE_MAX_PERIOD_SIZE     8192\n"
            "#define CAPTURE_MIN_PERIOD_SIZE     4096\n"
            "\n"
            "#define MAX_BUFFER (CAPTURE_MAX_PERIOD_SIZE * CAPTURE_MAX_NUM_PERIODS)\n"
            "#define MIN_BUFFER MAX_BUFFER\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            header = source / "sound/soc/amd/renoir/rn_acp3x.h"
            header.parent.mkdir(parents=True)
            header.write_text(original)
            subprocess.run(
                ["patch", "--batch", "--fuzz=0", "-p1",
                 "-i", str(recipe_patch("renoir-capture-buffers.patch"))],
                cwd=source, check=True, capture_output=True, text=True,
            )
            text = header.read_text()
        self.assertEqual(text, original.replace(
            "CAPTURE_MIN_NUM_PERIODS     4", "CAPTURE_MIN_NUM_PERIODS     2").replace(
            "CAPTURE_MIN_PERIOD_SIZE     4096", "CAPTURE_MIN_PERIOD_SIZE     1024"))
        limits = {name: int(value) for directive, name, value in
                  (line.split() for line in text.splitlines() if line.startswith("#define CAPTURE_"))}
        for frames, periods in ((480, 2), (960, 2), (512, 4), (1024, 4)):
            with self.subTest(frames=frames, periods=periods):
                period_bytes = frames * 2 * 4
                self.assertGreaterEqual(periods, limits["CAPTURE_MIN_NUM_PERIODS"])
                self.assertLessEqual(periods, limits["CAPTURE_MAX_NUM_PERIODS"])
                self.assertGreaterEqual(period_bytes, limits["CAPTURE_MIN_PERIOD_SIZE"])
                self.assertLessEqual(period_bytes, limits["CAPTURE_MAX_PERIOD_SIZE"])
                self.assertLessEqual(period_bytes * periods, 32768)
        self.assertEqual(limits, {
            "CAPTURE_MIN_NUM_PERIODS": 2, "CAPTURE_MAX_NUM_PERIODS": 4,
            "CAPTURE_MIN_PERIOD_SIZE": 1024, "CAPTURE_MAX_PERIOD_SIZE": 8192,
        })

    def test_patch_is_in_kernel_source_inputs(self):
        result = inspect_kernel_recipes()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("hardware/drivers/renoir-acp/renoir-capture-buffers.patch",
                      result.stdout.splitlines()[0].split())


if __name__ == "__main__":
    unittest.main()
