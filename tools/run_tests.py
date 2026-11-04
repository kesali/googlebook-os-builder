#!/usr/bin/env python3
"""Run generic and recipe-local unittest files; never build images or access devices."""

import argparse
import importlib.util
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]


def test_files(paths):
    files = set()
    for path in paths:
        path = path.resolve()
        if not path.is_relative_to(REPO):
            raise ValueError(f"Test path is outside the repository: {path}")
        if path.is_file() and path.match("test_*.py"):
            files.add(path)
        elif path.is_dir():
            discovered = set(path.rglob("test_*.py"))
            if not discovered:
                raise ValueError(f"No test files in {path}")
            files.update(discovered)
        else:
            raise ValueError(f"Expected a test_*.py file or test directory: {path}")
    return sorted(files)


def load_suite(files):
    suite = unittest.TestSuite()
    for path in files:
        # Recipe names and basenames may repeat; use the full relative path as module identity.
        name = ".".join(path.relative_to(REPO).with_suffix("").parts)
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        tests = unittest.defaultTestLoader.loadTestsFromModule(module)
        if not tests.countTestCases():
            raise ValueError(f"No tests collected from {path}")
        suite.addTests(tests)
    return suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="Test files or directories; default: all")
    args = parser.parse_args()
    paths = args.paths or [
        REPO / "tests",
        *sorted((REPO / "hardware").glob("*/tests")),
        *sorted((REPO / "hardware/drivers").glob("*/tests")),
    ]
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(REPO / "tests"))
    try:
        suite = load_suite(test_files(paths))
    except (ValueError, ImportError) as error:
        parser.exit(1, f"test discovery: {error}\n")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
