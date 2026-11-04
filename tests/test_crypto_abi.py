"""Verify crypto ABI failures using fake readelf output, never target libraries."""

import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import crypto_abi


def symbol(name="SHA256", kind="FUNC", binding="GLOBAL", size=16, section="12"):
    return f"1: 0000000000001000 {size} {kind} {binding} DEFAULT {section} {name}\n"


class CryptoAbiTests(unittest.TestCase):
    def compare(self, original, replacement):
        outputs = [subprocess.CompletedProcess([], 0, stdout=text)
                   for text in (original, replacement)]
        with patch.object(crypto_abi.subprocess, "run", side_effect=outputs):
            with contextlib.redirect_stdout(io.StringIO()):
                crypto_abi.check("original", "replacement")

    def test_function_code_size_and_additional_exports_can_differ(self):
        self.compare(symbol(), symbol(size=32) + symbol("extra"))

    def test_missing_export_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA256"):
            self.compare(symbol(), symbol("different"))

    def test_binding_kind_visibility_and_object_size_must_match(self):
        cases = [
            (symbol(), symbol(binding="WEAK")),
            (symbol(), symbol(kind="OBJECT")),
            (symbol(kind="OBJECT"), symbol(kind="OBJECT", size=32)),
            (symbol(), symbol().replace("DEFAULT", "PROTECTED")),
        ]
        for original, replacement in cases:
            with self.subTest(replacement=replacement):
                with self.assertRaises(ValueError):
                    self.compare(original, replacement)

    def test_undefined_and_local_symbols_do_not_satisfy_export(self):
        for replacement in (symbol(section="UND"), symbol(binding="LOCAL")):
            with self.subTest(replacement=replacement):
                with self.assertRaises(ValueError):
                    self.compare(symbol(), replacement + symbol("other"))

    def test_symbol_versions_are_not_discarded(self):
        with self.assertRaises(ValueError):
            self.compare(symbol("SHA256@@VERSION_1"), symbol("SHA256@@VERSION_2"))

    def test_autofdo_marker_is_the_only_ignored_export(self):
        self.compare(symbol() + symbol("__llvm_fs_discriminator__"), symbol())

    def test_empty_symbol_table_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no dynamic exports"):
            self.compare("", symbol())

    def test_readelf_failure_propagates(self):
        with patch.object(crypto_abi.subprocess, "run",
                          side_effect=subprocess.CalledProcessError(1, ["readelf"])):
            with self.assertRaises(subprocess.CalledProcessError):
                crypto_abi.exports("not-an-elf")


if __name__ == "__main__":
    unittest.main()
