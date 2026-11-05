"""Check log retrieval with fake debugfs and device metadata, never physical disks."""

import json
import hashlib
import io
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import laptop_logs


class LaptopLogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / "logs"
        self.device = Path("/dev/fake17")
        self.identity = b"5884b0b7-e644-4815-8084-85d32391a734\n"
        self.files = {"boot-id": self.identity, "hardware.txt": b"card=acp\n"}
        self.root_entries = {"current": (stat.S_IFDIR | 0o700, 0),
                             "previous": (stat.S_IFDIR | 0o700, 0)}
        self.entries = {name: (stat.S_IFREG | 0o600, len(data))
                        for name, data in self.files.items()}
        self.device_patch = patch.object(laptop_logs, "log_device",
                                         return_value=(self.device, "ext4"))
        self.device_patch.start()
        self.addCleanup(self.device_patch.stop)

    def listing(self, device, path):
        return self.root_entries if path == "/gbos-builder-bootlog" else self.entries

    def read(self, device, request):
        return self.files[request.rsplit("/", 1)[-1]]

    def retrieve(self):
        with patch.object(laptop_logs, "directory", side_effect=self.listing), \
                patch.object(laptop_logs, "debugfs", side_effect=self.read):
            return laptop_logs.retrieve({}, self.output)

    def test_reads_both_boots_and_preserves_copies_with_latest_link(self):
        first = self.retrieve()
        for boot in ("current", "previous"):
            self.assertEqual((first / boot / "hardware.txt").read_bytes(), b"card=acp\n")
        second = self.retrieve()
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_dir())
        self.assertEqual((self.output / "latest").resolve(), second)

    def test_previous_boot_is_optional(self):
        del self.root_entries["previous"]
        self.assertFalse((self.retrieve() / "previous").exists())

    def test_partial_touchpad_capture_is_retrieved_without_treating_it_as_finished(self):
        data = b"status=capturing\n[   60.000002] 0000 0000 00000000\n"
        self.files["touchpad.log"] = data
        self.entries["touchpad.log"] = (stat.S_IFREG | 0o600, len(data))
        destination = self.retrieve()
        for boot in ("current", "previous"):
            self.assertEqual((destination / boot / "touchpad.log").read_bytes(), data)

    def test_unfinished_snapshot_does_not_block_completed_logs(self):
        self.entries["hardware.txt.tmp"] = (stat.S_IFREG | 0o600, 399)
        destination = self.retrieve()
        for boot in ("current", "previous"):
            self.assertEqual((destination / boot / "hardware.txt").read_bytes(), b"card=acp\n")
            self.assertFalse((destination / boot / "hardware.txt.tmp").exists())
        self.assertEqual((self.output / "latest").resolve(), destination)

    def test_temporary_snapshot_still_requires_safe_type_and_size(self):
        for entry in ((stat.S_IFLNK | 0o777, 5), (stat.S_IFREG | 0o600, (10 << 20) + 1)):
            with self.subTest(entry=entry):
                self.entries["hardware.txt.tmp"] = entry
                with self.assertRaisesRegex(ValueError, "Invalid temporary hardware snapshot"):
                    self.retrieve()

    def test_rejects_symlinks_unknown_files_and_oversized_logs_before_reading(self):
        for name, entry in (("hardware.txt", (stat.S_IFLNK | 0o777, 5)),
                            ("touchpad.log", (stat.S_IFLNK | 0o777, 5)),
                            ("private-state", (stat.S_IFREG | 0o600, 5)),
                            ("kernel.log", (stat.S_IFREG | 0o600, (10 << 20) + 1))):
            with self.subTest(name=name):
                original = self.entries.copy()
                self.entries[name] = entry
                with patch.object(laptop_logs, "directory", side_effect=self.listing), \
                        patch.object(laptop_logs, "debugfs") as read:
                    with self.assertRaises(ValueError):
                        laptop_logs.retrieve({}, self.output)
                    read.assert_not_called()
                self.entries = original

    def test_failed_read_does_not_replace_latest(self):
        original = self.retrieve()
        with patch.object(laptop_logs, "directory", side_effect=self.listing), \
                patch.object(laptop_logs, "debugfs", return_value=b"short"):
            with self.assertRaises(ValueError):
                laptop_logs.retrieve({}, self.output)
        self.assertEqual((self.output / "latest").resolve(), original)

    def test_debugfs_errors_are_not_success_even_with_exit_zero(self):
        result = subprocess.CompletedProcess([], 0, b"", b"debugfs 1.47\ncat: File not found\n")
        with patch.object(laptop_logs.subprocess, "run", return_value=result) as run:
            with self.assertRaisesRegex(ValueError, "File not found"):
                laptop_logs.debugfs(self.device, "cat /gbos-builder-bootlog/current/boot-id")
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["sudo", "--", "debugfs", "-R"])
        self.assertNotIn("-w", command)

    def test_parses_directory_listing(self):
        listing = b"/12/040700/0/0/./0/\n/13/100600/0/0/boot-id/37/\n"
        with patch.object(laptop_logs, "debugfs", return_value=listing):
            self.assertEqual(laptop_logs.directory(self.device, "/gbos-builder-bootlog/current"),
                             {"boot-id": (0o100600, 37)})

    def test_reads_real_ext4_image_without_sudo_or_mounts(self):
        root = self.output.parent
        seed = root / "seed"
        boot = seed / "gbos-builder-bootlog/current"
        boot.mkdir(parents=True)
        for name, data in self.files.items():
            (boot / name).write_bytes(data)
        image = root / "metadata.img"
        with image.open("wb") as stream:
            stream.truncate(8 << 20)
        subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", "-d", str(seed), str(image)],
                       check=True, capture_output=True)
        run = subprocess.run

        def read_image(arguments, **kwargs):
            self.assertEqual(arguments[:4], ["sudo", "--", "debugfs", "-R"])
            self.assertNotIn("-w", arguments)
            return run(arguments[2:-1] + [str(image)], **kwargs)

        with patch.object(laptop_logs.subprocess, "run", side_effect=read_image):
            destination = laptop_logs.retrieve({}, self.output)
        self.assertEqual((destination / "current/hardware.txt").read_bytes(), b"card=acp\n")

    def test_rejects_missing_or_ambiguous_metadata(self):
        self.device_patch.stop()
        selected = {"name": "/dev/fake", "serial": "serial", "model": "Test",
                    "size": 1000, "maj:min": "8:0", "tran": "usb", "children": []}
        for children in ([], [{"name": "/dev/fake1", "partlabel": "metadata"}] * 2):
            with self.subTest(children=children), \
                    patch.object(laptop_logs, "disks", return_value=[selected]), \
                    patch.object(laptop_logs, "check_unused"), \
                    patch.object(laptop_logs, "run", return_value=json.dumps({
                        "blockdevices": [{"name": "/dev/fake", "children": children}]})):
                with self.assertRaisesRegex(ValueError, "exactly one"):
                    laptop_logs.log_device(selected)

    def test_reads_real_fat32_image_without_sudo_mounts_or_source_writes(self):
        image = self.output.parent / "logs.img"
        with image.open("wb") as stream:
            stream.truncate(256 << 20)
        subprocess.run(["mkfs.vfat", "-F", "32", "-s", "1", "-n", "GBOS-LOGS", str(image)],
                       check=True, capture_output=True)
        subprocess.run(["mmd", "-i", str(image), "::/current", "::/previous"],
                       check=True, capture_output=True)
        for name, data in self.files.items():
            seed = self.output.parent / name
            seed.write_bytes(data)
            for boot in ("current", "previous"):
                subprocess.run(["mcopy", "-i", str(image), str(seed), f"::/{boot}/{name}"],
                               check=True, capture_output=True)
        before = image.stat()
        with image.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").digest()
        run = subprocess.run
        popen = subprocess.Popen

        def direct_run(arguments, **kwargs):
            self.assertEqual(arguments[:2], ["sudo", "--"])
            return run(arguments[2:], **kwargs)

        def direct_popen(arguments, **kwargs):
            if arguments[:2] == ["sudo", "--"]:
                arguments = arguments[2:]
            self.assertIn(arguments[0], ("mdir", "mtype"))
            return popen(arguments, **kwargs)

        with patch.object(laptop_logs, "log_device", return_value=(image, "vfat")), \
                patch.object(laptop_logs.subprocess, "run", side_effect=direct_run), \
                patch.object(laptop_logs.subprocess, "Popen", side_effect=direct_popen):
            destination = laptop_logs.retrieve({}, self.output)
        self.assertEqual((destination / "current/hardware.txt").read_bytes(), b"card=acp\n")
        self.assertEqual((destination / "previous/boot-id").read_bytes(), self.identity)
        self.assertEqual(image.stat().st_mtime_ns, before.st_mtime_ns)
        with image.open("rb") as stream:
            self.assertEqual(hashlib.file_digest(stream, "sha256").digest(), digest)

    def test_fat_directory_rejects_bad_entries_and_reports_reader_errors(self):
        for result in (
                subprocess.CompletedProcess([], 0, "::/current/boot-id\n::/current/boot-id\n", ""),
                subprocess.CompletedProcess([], 0, "::/elsewhere/secret\n", ""),
                subprocess.CompletedProcess([], 0, "", "FAT damaged"),
                subprocess.CompletedProcess([], 1, "", "Cannot read")):
            with self.subTest(result=result), \
                    patch.object(laptop_logs.subprocess, "run", return_value=result), \
                    self.assertRaises(ValueError):
                laptop_logs.fat_directory(self.device, "/current")

    def test_fat_read_is_bounded_and_reports_failures(self):
        for data, error, status in (
                (bytes((10 << 20) + 1), b"", 0),
                (b"", b"FAT damaged", 0), (b"", b"", 1)):
            with self.subTest(length=len(data), status=status):
                process = MagicMock()
                process.__enter__.return_value = process
                process.stdout = io.BytesIO(data)
                process.communicate.return_value = (b"", error)
                process.returncode = status
                with patch.object(laptop_logs.subprocess, "Popen", return_value=process), \
                        self.assertRaises(ValueError):
                    laptop_logs.fat_read(self.device, "/current/kernel.log")
                if len(data) > 10 << 20:
                    process.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
