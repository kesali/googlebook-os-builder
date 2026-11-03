"""Exercise USB update planning and writes on regular files, never real disks or mounts."""

from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import update_usb
import install_usb
from deploy import COMPONENTS, bundle, install
from lp import Extent, LP_TARGET_TYPE_LINEAR, LpMetadataGeometry, Partition


class USBUpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.image = self.root / "image"
        self.target = self.root / "usb"
        self.image.write_bytes(b"I" * (96 * 512))
        self.target.write_bytes(b"T" * (104 * 512))
        self.layout = {
            "id": "disk-uuid", "firstlba": 34, "lastlba": 62,
            "partitions": [
                {"name": "userdata", "start": 88, "size": 8, "node": "data", "uuid": "data-id"},
                {"name": "super", "start": 2, "size": 70, "node": "super", "uuid": "super-id"},
                {"name": "vbmeta_a", "start": 80, "size": 1, "node": "vbmeta", "uuid": "vbmeta-id"},
                {"name": "EFI-SYSTEM", "start": 82, "size": 2,
                 "node": "esp", "uuid": "boot-id"},
            ],
        }
        self.logical = [
            Partition(name, "default", [Extent(1, LP_TARGET_TYPE_LINEAR, 28 + i * 2, 0)])
            for i, name in enumerate(update_usb.OS_PARTITIONS[:-1])
        ]
        # A multi-extent OS partition, with a preserved gap between its extents.
        self.logical[1].extents.append(Extent(1, LP_TARGET_TYPE_LINEAR, 39, 0))
        with self.image.open("r+b") as source:
            source.seek(2 * 512 + 4096)
            source.write(LpMetadataGeometry.pack(
                0x616C4467, LpMetadataGeometry.size, bytes(32), 512, 1, 4096,
            ))
        with self.image.open("rb") as source, patch.object(
            update_usb, "read_partitions", return_value=self.logical
        ):
            self.ranges, self.metadata = update_usb.os_extents(source, self.layout)
        with self.target.open("r+b") as target:
            target.seek(self.metadata[0])
            target.write(self.image.read_bytes()[self.metadata[0]:sum(self.metadata)])
            target.seek(82 * 512 + 71)
            target.write(b"DALI-BOOT  FAT32   ")
        inputs = self.root / "inputs"
        inputs.mkdir()
        for name in COMPONENTS:
            (inputs / name).write_bytes(name.encode())
        (inputs / "menu.cfg").write_bytes(b"kernel=@KERNEL@ initramfs=@INITRAMFS@")
        self.bundle = self.root / "bundle"
        bundle([inputs / name for name in COMPONENTS], self.bundle, "android")
        self.boot = self.root / "boot"
        self.boot.mkdir()
        install(self.bundle, self.boot, initialize=True)

    def test_only_usb_whole_disks_are_offered(self):
        nodes = [{"type": kind, "tran": transport} for kind, transport in (
            ("disk", "usb"), ("part", "usb"), ("disk", "nvme"), ("disk", "sata"),
        )]
        self.assertEqual(update_usb.usb_disks(nodes), nodes[:1])

    def test_selection_never_defaults_to_a_disk(self):
        node = {"type": "disk", "tran": "usb", "name": "/dev/fake",
                "size": 1000, "serial": "serial", "model": "Test", "ro": False}
        with patch.object(update_usb, "disks", return_value=[node]), \
                patch("builtins.input", return_value=""):
            self.assertIsNone(update_usb.choose())
        with patch.object(update_usb, "disks", return_value=[node]), \
                patch("builtins.input", return_value="0"):
            with self.assertRaisesRegex(ValueError, "Invalid USB selection"):
                update_usb.choose()
        with patch.object(update_usb, "disks", return_value=[]):
            with self.assertRaisesRegex(ValueError, "No USB"):
                update_usb.choose()

    def test_grown_userdata_is_accepted_but_no_other_layout_changes(self):
        target = copy.deepcopy(self.layout)
        target["partitions"][0]["size"] += 8
        for part in target["partitions"]:
            part["node"] = "/dev/fake"
        update_usb.check_layout(self.layout, target)
        cases = []
        for key, value in (("start", 23), ("size", 7), ("uuid", "changed")):
            changed = copy.deepcopy(target)
            changed["partitions"][0][key] = value
            cases.append(changed)
        changed = copy.deepcopy(target)
        changed["partitions"][1]["size"] += 1
        cases.append(changed)
        changed = copy.deepcopy(target)
        changed["id"] = "different-disk"
        cases.append(changed)
        cases.append({**target, "partitions": target["partitions"][:-1]})
        for changed in cases:
            with self.subTest(layout=changed), self.assertRaises(ValueError):
                update_usb.check_layout(self.layout, changed)

    def test_unsupported_out_of_bounds_and_overlapping_extents_are_rejected(self):
        for extent in (Extent(1, 1, 28, 0), Extent(1, 0, 28, 1),
                       Extent(0, 0, 28, 0), Extent(100, 0, 28, 0),
                       Extent(1, 0, 30, 0), Extent(1, 0, 1, 0)):
            logical = copy.deepcopy(self.logical)
            logical[0].extents = [extent]
            with patch.object(update_usb, "read_partitions", return_value=logical), \
                    self.image.open("rb") as source, self.assertRaises(ValueError):
                update_usb.os_extents(source, self.layout)

    def test_duplicate_logical_partition_names_are_rejected(self):
        logical = copy.deepcopy(self.logical)
        logical.append(Partition(logical[0].name, "default", [Extent(1, 0, 45, 0)]))
        with patch.object(update_usb, "read_partitions", return_value=logical), \
                self.image.open("rb") as source, \
                self.assertRaisesRegex(ValueError, "Duplicate liblp partition"):
            update_usb.os_extents(source, self.layout)

    def test_changed_metadata_refuses_before_writing(self):
        before = self.target.read_bytes()
        with self.image.open("rb") as source, self.target.open("rb") as target:
            with self.assertRaisesRegex(ValueError, "metadata differs"):
                update_usb.plan_os(source, target, self.ranges, (0, 512))
        self.assertEqual(self.target.read_bytes(), before)

    def test_multi_extent_update_preserves_every_other_byte_and_repeat_writes_nothing(self):
        before = self.target.read_bytes()
        with self.image.open("rb") as source, self.target.open("r+b", buffering=0) as target:
            updates = update_usb.plan_os(source, target, self.ranges, self.metadata)
            self.assertEqual([name for name, _, _ in updates], list(update_usb.OS_PARTITIONS))
            guard, flush = Mock(), Mock()
            update_usb.write_os(source, target, updates, guard, flush)
            self.assertEqual(guard.call_count, 5)
            self.assertEqual(flush.call_count, 5)
            timestamp = self.target.stat().st_mtime_ns
            self.assertEqual(update_usb.plan_os(source, target, self.ranges, self.metadata), [])
            self.assertEqual(self.target.stat().st_mtime_ns, timestamp)
        after = self.target.read_bytes()
        image = self.image.read_bytes()
        updated = set()
        for extents in self.ranges.values():
            for offset, length in extents:
                self.assertEqual(after[offset:offset + length], image[offset:offset + length])
                updated.update(range(offset, offset + length))
        for index, value in enumerate(before):
            if index not in updated:
                self.assertEqual(after[index], value, f"Protected byte {index}")

    def test_readback_failure_is_reported(self):
        with self.image.open("rb") as source, self.target.open("r+b", buffering=0) as target:
            updates = update_usb.plan_os(source, target, self.ranges, self.metadata)
            with patch.object(update_usb, "disk_hash", return_value="corrupt"):
                with self.assertRaisesRegex(OSError, "read-back differs"):
                    update_usb.write_os(source, target, updates[:1], Mock(), Mock())

    def test_no_write_when_device_becomes_busy(self):
        before = self.target.read_bytes()
        with self.image.open("rb") as source, self.target.open("r+b", buffering=0) as target:
            updates = update_usb.plan_os(source, target, self.ranges, self.metadata)
            with self.assertRaisesRegex(ValueError, "busy"):
                update_usb.write_os(source, target, updates,
                                    Mock(side_effect=ValueError("busy")), Mock())
        self.assertEqual(self.target.read_bytes(), before)

    def test_mounted_swap_and_holder_devices_are_rejected(self):
        node = {"name": "/dev/fake", "maj:min": "1:2", "mountpoints": [],
                "children": [{"name": "/dev/fake1", "maj:min": "1:3",
                              "mountpoints": ["/media/test"]}]}
        for mount in ("/media/test", "[SWAP]"):
            node["children"][0]["mountpoints"] = [mount]
            with patch.object(Path, "iterdir", return_value=iter([])):
                with self.assertRaisesRegex(ValueError, "in use"):
                    update_usb.check_unused(node)
        with patch.object(Path, "iterdir", return_value=iter([Path("holder")])):
            with self.assertRaisesRegex(ValueError, "holders"):
                update_usb.check_unused(node)

    def test_device_identity_change_is_rejected(self):
        selected = {"name": "/dev/fake", "type": "disk", "tran": "usb",
                    "maj:min": "8:0", "serial": "original", "model": "Test", "size": 4096}
        with patch.object(update_usb, "disks",
                          return_value=[{**selected, "serial": "different"}]):
            with self.assertRaisesRegex(ValueError, "changed"):
                update_usb.check_identity(selected, Mock())

    def test_partition_reader_rejects_non_gpt_and_non_sector_tables(self):
        layout = {**self.layout, "label": "gpt", "sectorsize": 512, "unit": "sectors"}
        for key, value in (("label", "dos"), ("sectorsize", 4096), ("unit", "bytes")):
            with self.subTest(key=key), patch.object(
                update_usb, "run",
                return_value=json.dumps({"partitiontable": {**layout, key: value}}),
            ), self.assertRaises(ValueError):
                update_usb.table(self.image)
        duplicate = copy.deepcopy(layout)
        duplicate["partitions"].append(copy.deepcopy(duplicate["partitions"][0]))
        with patch.object(
            update_usb, "run", return_value=json.dumps({"partitiontable": duplicate}),
        ), self.assertRaisesRegex(ValueError, "Duplicate GPT partition names"):
            update_usb.table(self.image)

    def test_source_symlink_and_device_are_rejected_before_selection(self):
        link = self.root / "link"
        link.symlink_to(self.image)
        with patch.object(update_usb.os, "geteuid", return_value=0), \
                patch.object(update_usb.shutil, "which", return_value="/unused"), \
                patch.object(update_usb, "choose", side_effect=AssertionError("must not select")):
            for path in (link, Path("/dev/null")):
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "regular built image"):
                    update_usb.update(path, self.bundle)

    def test_failed_unmount_never_recursively_cleans_the_filesystem(self):
        mountpoint = self.root / "mount"
        mountpoint.mkdir()
        protected = mountpoint / "keep"
        protected.write_text("must survive")
        failure = subprocess.CalledProcessError(1, ["umount"])
        with patch.object(update_usb.tempfile, "mkdtemp", return_value=str(mountpoint)), \
                patch.object(update_usb.subprocess, "run", side_effect=[Mock(), failure]):
            with self.assertRaises(subprocess.CalledProcessError):
                with update_usb.boot_mount(Path("/dev/fake")):
                    pass
        self.assertEqual(protected.read_text(), "must survive")

    def test_boot_preflight_does_not_change_files_or_timestamps(self):
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.boot.rglob("*") if p.is_file()}
        (self.bundle / "kernel").write_bytes(b"new")
        manifest = json.loads((self.bundle / "manifest.json").read_text())
        manifest["sha256"]["kernel"] = hashlib.sha256(b"new").hexdigest()
        (self.bundle / "manifest.json").write_text(json.dumps(manifest))
        planned = install(self.bundle, self.boot, dry_run=True)
        self.assertEqual(len(planned), 2)
        self.assertEqual(planned[-1], "dali/grub.cfg")
        self.assertEqual(before, {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                                  for p in self.boot.rglob("*") if p.is_file()})
        self.assertEqual(install(self.bundle, self.boot), planned)
        self.assertEqual(install(self.bundle, self.boot, dry_run=True), [])

    def test_confirmation_and_combined_update_on_regular_file_fixtures(self):
        selected = {
            "name": str(self.target), "type": "disk", "tran": "usb", "maj:min": "8:0",
            "serial": "test-serial", "model": "Test", "size": self.target.stat().st_size,
            "ro": False, "children": [{"name": "esp"}],
        }

        @contextmanager
        def fake_mount(device, writable=False):
            yield self.boot

        @contextmanager
        def fake_snapshot(path):
            yield path

        with patch.object(update_usb.os, "geteuid", return_value=0), \
                patch.object(update_usb.shutil, "which", return_value="/unused"), \
                patch.object(update_usb, "choose", return_value=selected), \
                patch.object(update_usb.stat, "S_ISBLK", return_value=True), \
                patch.object(update_usb, "check_identity", return_value=selected), \
                patch.object(update_usb, "check_unused"), \
                patch.object(update_usb, "table", return_value=self.layout), \
                patch.object(update_usb, "read_partitions", return_value=self.logical), \
                patch.object(update_usb.subprocess, "run",
                             return_value=subprocess.CompletedProcess([], 0, "", "")), \
                patch.object(update_usb.fcntl, "ioctl", return_value=(512).to_bytes(4, "little")), \
                patch.object(update_usb, "boot_mount", side_effect=fake_mount) as mounts, \
                patch.object(update_usb, "snapshot_bundle", side_effect=fake_snapshot):
            before = self.target.read_bytes()
            boot_before = {p: p.read_bytes() for p in self.boot.rglob("*") if p.is_file()}
            for answer in ("", "n", "no", "wrong confirmation", "UPDATE test-serial"):
                with self.subTest(answer=answer), patch("builtins.input", return_value=answer) as prompt:
                    update_usb.update(self.image, self.bundle)
                    prompt.assert_called_once_with(
                        f"Write updates to {self.target} (Test, test-serial)? [y/N] ")
                    self.assertEqual(self.target.read_bytes(), before)
                    self.assertEqual({p: p.read_bytes() for p in boot_before}, boot_before)
                    self.assertFalse(any(call.kwargs.get("writable") for call in mounts.call_args_list))
            for answer in ("y", "yes", "Y", " YES "):
                with self.subTest(answer=answer):
                    self.target.write_bytes(before)
                    # An updated boot menu must be installed alongside the OS.
                    (self.boot / "dali/grub.cfg").write_bytes(b"old boot menu")
                    with patch("builtins.input", return_value=answer):
                        update_usb.update(self.image, self.bundle)
                    self.assertNotEqual(self.target.read_bytes(), before)
                    self.assertEqual(install(self.bundle, self.boot, dry_run=True), [])
            timestamp = self.target.stat().st_mtime_ns
            with patch("builtins.input", side_effect=AssertionError("no confirmation for a no-op")):
                update_usb.update(self.image, self.bundle)
            self.assertEqual(self.target.stat().st_mtime_ns, timestamp)


class USBGPTTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.image = self.root / "image"
        self.target = self.root / "usb"
        with self.image.open("wb") as stream:
            stream.truncate(16 * 1024 * 1024)
        subprocess.run(
            ["sfdisk", str(self.image)],
            input="label: gpt\nsize=1MiB, name=test\n",
            text=True, check=True, capture_output=True,
        )
        self.layout = update_usb.table(self.image)
        subprocess.run(["sfdisk", "--verify", str(self.image)],
                       check=True, capture_output=True)
        shutil.copyfile(self.image, self.target)
        with self.target.open("ab") as stream:
            stream.write(b"T" * (1024 * 1024))

    def verify(self):
        with self.image.open("rb") as source, self.target.open("rb") as target:
            update_usb.verify_target_gpt(
                source, target, self.layout, self.target, self.target.stat().st_size,
            )

    def test_raw_flash_to_larger_target_verifies_without_any_writes(self):
        size = self.image.stat().st_size
        expected = hashlib.sha256(self.image.read_bytes()).hexdigest()
        with self.image.open("rb") as source, self.target.open("r+b") as target:
            install_usb.flash(source, target, size, expected, Mock(), Mock())
        before = self.target.read_bytes()
        timestamp = self.target.stat().st_mtime_ns
        result = subprocess.run(["sfdisk", "--verify", str(self.target)], capture_output=True)
        self.assertIn(b"MyLBA mismatch", result.stderr)
        with patch.object(update_usb.subprocess, "run",
                          side_effect=AssertionError("must compare verified GPT bytes")):
            self.verify()
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(self.target.stat().st_mtime_ns, timestamp)

    def test_changed_mbr_headers_and_arrays_never_use_the_exception(self):
        original = self.target.read_bytes()
        end = (self.layout["lastlba"] + 1) * 512
        for offset in (446, 512, 1024, end, self.image.stat().st_size - 512):
            with self.subTest(offset=offset):
                changed = bytearray(original)
                changed[offset] ^= 1
                self.target.write_bytes(changed)
                failure = subprocess.CompletedProcess([], 1, "", "GPT error")
                with patch.object(update_usb.subprocess, "run", return_value=failure) as verify:
                    with self.assertRaisesRegex(ValueError, "GPT error"):
                        self.verify()
                    verify.assert_called_once_with(
                        ["sfdisk", "--verify", str(self.target)],
                        check=False, capture_output=True, text=True,
                    )
                self.assertEqual(self.target.read_bytes(), changed)

    def test_relocated_gpt_and_equal_size_targets_use_normal_verification(self):
        subprocess.run(["sfdisk", "--relocate", "gpt-bak-std", str(self.target)],
                       check=True, capture_output=True)
        with patch.object(update_usb.subprocess, "run",
                          wraps=subprocess.run) as verify:
            self.verify()
            verify.assert_called_once()
        shutil.copyfile(self.image, self.target)
        with patch.object(update_usb.subprocess, "run",
                          wraps=subprocess.run) as verify:
            self.verify()
            verify.assert_called_once()

    def test_source_metadata_bounds_are_checked(self):
        for bounds in ({"firstlba": 0}, {"lastlba": self.image.stat().st_size // 512}):
            with self.subTest(bounds=bounds):
                self.layout.update(bounds)
                with self.assertRaisesRegex(ValueError, "metadata bounds"):
                    self.verify()

    def test_verifier_diagnostics_fail_even_when_exit_status_is_zero(self):
        result = subprocess.CompletedProcess([], 0, "", "1 error detected.\n")
        with patch.object(update_usb.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(ValueError, "1 error detected"):
                update_usb.verify_gpt(self.image)


if __name__ == "__main__":
    unittest.main()
