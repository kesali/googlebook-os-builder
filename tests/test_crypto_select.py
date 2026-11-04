"""Verify CPU-based crypto selection without changing system properties or mounts."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SELECTOR = REPO / "android/system_ext/crypto-select.sh"


class CryptoSelectorTests(unittest.TestCase):
    def run_selector(self, cpuinfo_text):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        work = Path(temporary.name)
        cpuinfo = work / "cpuinfo"
        cpuinfo.write_text(cpuinfo_text)
        fake_bin = work / "bin"
        fake_bin.mkdir()
        property_log = work / "property.log"
        setprop = fake_bin / "setprop"
        setprop.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$PROPERTY_LOG"\n')
        setprop.chmod(0o755)
        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"
        environment["PROPERTY_LOG"] = str(property_log)
        result = subprocess.run(
            ["/bin/sh", str(SELECTOR), str(cpuinfo)],
            capture_output=True, text=True, env=environment,
        )
        properties = property_log.read_text().splitlines() if property_log.exists() else []
        return result, properties

    def test_keeps_stock_when_every_cpu_has_sha_ni(self):
        result, properties = self.run_selector(
            "processor : 0\nflags : fpu sha_ni avx2\n\n"
            "processor : 1\nflags : fpu sha_ni avx2\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("keeping Google's SHA-NI libraries", result.stdout)
        self.assertEqual(properties, ["sys.gbos_builder.crypto.mode stock"])

    def test_uses_portable_pair_when_any_cpu_lacks_sha_ni(self):
        result, properties = self.run_selector(
            "processor : 0\nflags : fpu sha_ni avx2\n\n"
            "processor : 1\nflags : fpu avx2\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("using portable libraries", result.stdout)
        self.assertEqual(properties, ["sys.gbos_builder.crypto.mode portable"])

    def test_uses_portable_pair_when_cpu_flags_are_unavailable(self):
        result, properties = self.run_selector("processor : 0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("using portable libraries", result.stdout)
        self.assertEqual(properties, ["sys.gbos_builder.crypto.mode portable"])

    def test_uses_portable_pair_when_a_cpu_has_no_flags_record(self):
        result, properties = self.run_selector(
            "processor : 0\nflags : fpu sha_ni avx2\n\n"
            "processor : 1\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("using portable libraries", result.stdout)
        self.assertEqual(properties, ["sys.gbos_builder.crypto.mode portable"])

    def test_uses_portable_pair_when_cpuinfo_cannot_be_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing_cpuinfo = Path(temporary) / "missing-cpuinfo"
            property_log = Path(temporary) / "property.log"
            fake_bin = Path(temporary) / "bin"
            fake_bin.mkdir()
            setprop = fake_bin / "setprop"
            setprop.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$PROPERTY_LOG"\n')
            setprop.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"
            environment["PROPERTY_LOG"] = str(property_log)
            result = subprocess.run(
                ["/bin/sh", str(SELECTOR), str(missing_cpuinfo)],
                capture_output=True, text=True, env=environment,
            )
            properties = property_log.read_text().splitlines()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cannot read", result.stdout)
        self.assertEqual(properties, ["sys.gbos_builder.crypto.mode portable"])


if __name__ == "__main__":
    unittest.main()
