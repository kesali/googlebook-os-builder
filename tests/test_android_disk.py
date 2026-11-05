"""Verify compact GPT creation with sparse regular-file recovery fixtures, never devices."""

import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import android_disk


def layout(disk):
    return json.loads(subprocess.check_output(
        ["sfdisk", "--json", str(disk)], text=True))["partitiontable"]


def read_partition(disk, part, length):
    with disk.open("rb") as stream:
        stream.seek(part["start"] * 512)
        return stream.read(length)


class AndroidDiskTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.recovery = self.work / "recovery.img"
        self.output = self.work / "new/disk.img"
        names = [name for name in android_disk.PARTITIONS if name != android_disk.LOG_PARTITION]
        names += ["KERN-B", "ROOT-B", "KERN-C", "boot_b"]
        lines = ["label: gpt"]
        for name in names:
            size = 8 if name == "super" else 1
            kind = "U" if name == "EFI-SYSTEM" else "L"
            lines.append(f'size={size * 2048}, type={kind}, name="{name}"')
        with self.recovery.open("wb") as stream:
            stream.truncate(64 << 20)
        subprocess.run(["sfdisk", "--quiet", str(self.recovery)],
                       input="\n".join(lines) + "\n", text=True, check=True,
                       capture_output=True)
        self.original = layout(self.recovery)
        with self.recovery.open("r+b") as stream:
            for part in self.original["partitions"]:
                stream.seek(part["start"] * 512)
                stream.write((part["name"] + "-original").encode())

    def create(self):
        with patch.object(android_disk, "SUPER_BYTES", 8 << 20):
            android_disk.create(self.recovery, 1, self.output)

    def test_only_retained_partitions_are_repacked_with_original_ids_and_payloads(self):
        before = self.recovery.stat()
        self.create()
        table = layout(self.output)
        self.assertEqual(table["id"], self.original["id"])
        self.assertEqual(tuple(p["name"] for p in table["partitions"]), android_disk.PARTITIONS)
        originals = {p["name"]: p for p in self.original["partitions"]}
        for part in table["partitions"]:
            name = part["name"]
            with self.subTest(name=name):
                if name == android_disk.LOG_PARTITION:
                    self.assertEqual(part["size"] * 512, 256 << 20)
                    continue
                self.assertEqual(part["uuid"], originals[name]["uuid"])
                self.assertEqual(part["type"], originals[name]["type"])
                self.assertEqual(part["start"] % 2048, 0)
                if name in ("super", "metadata", "userdata"):
                    self.assertEqual(read_partition(self.output, part, 512), bytes(512))
                elif name != "EFI-SYSTEM":
                    self.assertEqual(read_partition(self.output, part, 512),
                                     read_partition(self.recovery, originals[name], 512))
        data = table["partitions"][-1]
        self.assertEqual(data["size"] * 512, 1 << 30)
        self.assertEqual(data["start"], max(p["start"] for p in table["partitions"]))
        attributes = {p["name"]: p.get("attrs", "") for p in table["partitions"]}
        self.assertEqual(attributes["vbmeta_a"], "GUID:48,49,50,51,56")
        self.assertEqual(attributes["vbmeta_b"], "")
        self.assertEqual((self.recovery.stat().st_size, self.recovery.stat().st_mtime_ns),
                         (before.st_size, before.st_mtime_ns))

    def test_boot_partition_is_real_fat32_with_two_builds_worth_of_room(self):
        self.create()
        esp = layout(self.output)["partitions"][0]
        self.assertEqual(esp["size"] * 512, 576 << 20)
        boot = read_partition(self.output, esp, 512)
        self.assertEqual(boot[71:90], b"GBOS-BOOT  FAT32   ")
        total, fat = struct.unpack_from("<II", boot, 32)
        reserved, = struct.unpack_from("<H", boot, 14)
        clusters = (total - reserved - boot[16] * fat) // boot[13]
        self.assertGreaterEqual(clusters, 65525)
        self.assertLessEqual(total, esp["size"])

    def test_logs_partition_is_fat32_and_precedes_userdata(self):
        self.create()
        parts = layout(self.output)["partitions"]
        logs = parts[-2]
        self.assertEqual(logs["name"], android_disk.LOG_PARTITION)
        self.assertEqual(logs["size"] * 512, 256 << 20)
        boot = read_partition(self.output, logs, 512)
        self.assertEqual(boot[71:90], b"GBOS-LOGS  FAT32   ")
        total, fat = struct.unpack_from("<II", boot, 32)
        reserved, = struct.unpack_from("<H", boot, 14)
        clusters = (total - reserved - boot[16] * fat) // boot[13]
        self.assertGreaterEqual(clusters, 65525)
        self.assertLessEqual(total, logs["size"])

    def test_existing_output_symlink_and_device_sources_are_refused(self):
        self.output.parent.mkdir()
        self.output.write_bytes(b"keep")
        with self.assertRaisesRegex(ValueError, "Refusing to replace"):
            self.create()
        self.assertEqual(self.output.read_bytes(), b"keep")
        link = self.work / "link.img"
        link.symlink_to(self.work / "missing.img")
        with self.assertRaisesRegex(ValueError, "Refusing to replace"):
            android_disk.create(self.recovery, 1, link)
        with self.assertRaisesRegex(ValueError, "regular file"):
            android_disk.create(Path("/dev/null"), 1, self.work / "other.img")

    def test_missing_partitions_unexpected_super_and_invalid_data_size_fail(self):
        for size in (0, -1, True):
            with self.subTest(size=size), self.assertRaises(ValueError):
                android_disk.compact_layout(self.original, size)
        with self.assertRaisesRegex(ValueError, "12 GiB"):
            android_disk.compact_layout(self.original, 1)
        self.original["partitions"].pop(0)
        with self.assertRaisesRegex(ValueError, "missing"):
            android_disk.compact_layout(self.original, 1)

    def test_creation_failure_does_not_publish_or_retain_scratch_output(self):
        with patch.object(android_disk.subprocess, "run",
                          side_effect=subprocess.CalledProcessError(1, ["sfdisk"])):
            with self.assertRaises(subprocess.CalledProcessError):
                self.create()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.work.glob("new/*.partial.*")))


if __name__ == "__main__":
    unittest.main()
