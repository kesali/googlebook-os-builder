"""Check log retrieval with fake debugfs and device metadata, never physical disks."""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

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
                                         return_value=(self.device, "ext4",
                                                       "/gbos-builder-bootlog"))
        self.device_patch.start()
        self.addCleanup(self.device_patch.stop)

    def listing(self, device, path):
        return self.root_entries if path.endswith("gbos-builder-bootlog") else self.entries

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

    def test_checks_boot_identity_before_other_files(self):
        self.entries = {"hardware.txt": self.entries["hardware.txt"],
                        "boot-id": self.entries["boot-id"]}
        with patch.object(laptop_logs, "directory", side_effect=self.listing), \
                patch.object(laptop_logs, "debugfs", side_effect=self.read) as read:
            laptop_logs.retrieve({}, self.output)
        self.assertTrue(read.call_args_list[0].args[1].endswith("/current/boot-id"))

    def test_previous_boot_is_optional(self):
        del self.root_entries["previous"]
        self.assertFalse((self.retrieve() / "previous").exists())

    def test_missing_current_still_saves_previous_without_updating_latest(self):
        del self.root_entries["current"]
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.retrieve()
        destination = next(self.output.iterdir())
        self.assertEqual((destination / "previous/boot-id").read_bytes(), self.identity)
        self.assertFalse((self.output / "latest").exists())

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

    def test_reads_real_ext4_logs_partition_without_sudo_or_mounts(self):
        root = self.output.parent / "ext4-seed"
        for boot in ("current", "previous"):
            directory = root / boot
            directory.mkdir(parents=True)
            for name, data in self.files.items():
                (directory / name).write_bytes(data)
        image = self.output.parent / "logs-ext4.img"
        with image.open("wb") as stream:
            stream.truncate(256 << 20)
        subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", "-b", "4096", "-m", "0",
                        "-L", "GBOS-LOGS", "-d", str(root), str(image)],
                       check=True, capture_output=True)
        run = subprocess.run

        def direct_read(arguments, **kwargs):
            self.assertEqual(arguments[:4], ["sudo", "--", "debugfs", "-R"])
            self.assertNotIn("-w", arguments)
            return run(arguments[2:], **kwargs)

        with patch.object(laptop_logs, "log_device",
                          return_value=(image, "ext4", "")), \
                patch.object(laptop_logs.subprocess, "run", side_effect=direct_read):
            destination = laptop_logs.retrieve({}, self.output)
        for boot in ("current", "previous"):
            self.assertEqual((destination / boot / "boot-id").read_bytes(), self.identity)
            self.assertEqual((destination / boot / "hardware.txt").read_bytes(), b"card=acp\n")

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

    def test_selects_ext4_logs_partition_and_root(self):
        self.device_patch.stop()
        selected = {"name": "/dev/fake", "serial": "serial", "model": "Test",
                    "size": 1000, "maj:min": "8:0", "tran": "usb", "children": [
                        {"name": "/dev/fake1", "maj:min": "8:1"},
                    ]}
        listing = {"blockdevices": [{"name": "/dev/fake", "children": [
            {"name": "/dev/fake1", "partlabel": "gbos_logs", "fstype": "ext4"},
        ]}]}
        device_stat = SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=os.makedev(8, 1))
        with patch.object(laptop_logs, "disks", return_value=[selected]), \
                patch.object(laptop_logs, "check_unused"), \
                patch.object(laptop_logs, "run", return_value=json.dumps(listing)) as run, \
                patch.object(Path, "stat", return_value=device_stat):
            self.assertEqual(laptop_logs.log_device(selected),
                             (Path("/dev/fake1"), "ext4", ""))
        self.assertIn("NAME,PARTLABEL,FSTYPE", run.call_args.args)

    def test_rejects_fat_log_partition(self):
        self.device_patch.stop()
        selected = {"name": "/dev/fake", "serial": "serial", "model": "Test",
                    "size": 1000, "maj:min": "8:0", "tran": "usb", "children": []}
        listing = {"blockdevices": [{"name": "/dev/fake", "children": [
            {"name": "/dev/fake1", "partlabel": "gbos_logs", "fstype": "vfat"},
        ]}]}
        with patch.object(laptop_logs, "disks", return_value=[selected]), \
                patch.object(laptop_logs, "check_unused"), \
                patch.object(laptop_logs, "run", return_value=json.dumps(listing)):
            with self.assertRaisesRegex(ValueError, "Unsupported diagnostic log filesystem: vfat"):
                laptop_logs.log_device(selected)

    def test_incomplete_current_does_not_block_readable_previous(self):
        root = {"current": (stat.S_IFDIR, 0), "previous": (stat.S_IFDIR, 0)}
        current = {"hardware.txt": (stat.S_IFREG, len(b"card=acp\n")),
                   "android.log": (stat.S_IFREG, 10)}
        previous = {"boot-id": (stat.S_IFREG, len(self.identity)),
                    "hardware.txt": (stat.S_IFREG, len(b"card=acp\n"))}

        def listing(device, path):
            return {"": root, "/current": current, "/previous": previous}[path]

        def read(device, request):
            if request.endswith("/android.log"):
                raise laptop_logs.LogReadError("Cannot read android.log")
            return self.identity if request.endswith("/boot-id") else b"card=acp\n"

        self.output.mkdir()
        (self.output / "old").mkdir()
        (self.output / "latest").symlink_to("old")
        with patch.object(laptop_logs, "log_device", return_value=(self.device, "ext4", "")), \
                patch.object(laptop_logs, "directory", side_effect=listing), \
                patch.object(laptop_logs, "debugfs", side_effect=read):
            with self.assertRaisesRegex(ValueError, "incomplete"):
                laptop_logs.retrieve({}, self.output)

        destination = next(path for path in self.output.iterdir()
                           if path.name not in ("old", "latest"))
        self.assertEqual((destination / "current/hardware.txt").read_bytes(), b"card=acp\n")
        self.assertFalse((destination / "current/android.log").exists())
        self.assertEqual((destination / "previous/boot-id").read_bytes(), self.identity)
        self.assertEqual((self.output / "latest").resolve(), self.output / "old")

if __name__ == "__main__":
    unittest.main()
