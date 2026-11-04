"""Verify recipe test discovery with temporary files, never hardware or images."""

import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import run_tests


class TestDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        override = patch.object(run_tests, "REPO", self.root)
        override.start()
        self.addCleanup(override.stop)
        modules = patch.dict(sys.modules)
        modules.start()
        self.addCleanup(modules.stop)
        search_path = patch.object(sys, "path", list(sys.path))
        search_path.start()
        self.addCleanup(search_path.stop)

    def write_test(self, path, assertion="True"):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "import unittest\n"
            "class Example(unittest.TestCase):\n"
            "    def test_value(self):\n"
            f"        self.assertTrue({assertion})\n"
        )
        return path

    def test_same_basename_in_different_recipes_runs_both(self):
        first = self.write_test("hardware/first/tests/test_audio.py")
        second = self.write_test("hardware/second/tests/test_audio.py", "False")
        suite = run_tests.load_suite(run_tests.test_files([first.parent, second.parent]))
        self.assertEqual(suite.countTestCases(), 2)
        with contextlib.redirect_stderr(io.StringIO()):
            result = unittest.TextTestRunner().run(suite)
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(len(result.failures), 1)

    def test_overlapping_paths_are_deduplicated(self):
        path = self.write_test("tests/test_example.py")
        self.assertEqual(run_tests.test_files([path, path.parent]), [path])

    def test_default_includes_generic_device_and_driver_tests_without_selection(self):
        generic = self.write_test("tests/test_example.py")
        (self.root / "recipe_runner_fixture.py").write_text("VALUE = 1\n")
        generic.write_text(generic.read_text() + "import recipe_runner_fixture\n")
        self.write_test("hardware/unselected-device/tests/test_example.py")
        self.write_test("hardware/drivers/unselected-driver/tests/test_example.py")
        with patch.object(sys, "argv", ["run_tests.py"]):
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                self.assertEqual(run_tests.main(), 0)
        self.assertIn("Ran 3 tests", output.getvalue())

    def test_invalid_missing_empty_and_external_paths_fail(self):
        empty = self.root / "empty"
        empty.mkdir()
        for path in (empty, self.root / "missing", self.root.parent):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    run_tests.test_files([path])

    def test_empty_test_module_is_not_success(self):
        path = self.root / "test_empty.py"
        path.write_text("import unittest\n")
        with self.assertRaisesRegex(ValueError, "No tests collected"):
            run_tests.load_suite([path])

    def test_import_error_is_not_swallowed(self):
        path = self.root / "test_broken.py"
        path.write_text("raise ImportError('broken recipe test')\n")
        with self.assertRaisesRegex(ImportError, "broken recipe test"):
            run_tests.load_suite([path])


if __name__ == "__main__":
    unittest.main()
