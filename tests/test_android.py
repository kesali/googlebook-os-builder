import fcntl
import hashlib
import json
from pathlib import Path
import sys
import struct
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from android_sync import copy_component, disk_hash, sync
from android_smoke import check_scanout
from lp import Extent, Partition, LP_TARGET_TYPE_LINEAR


class AndroidTests(unittest.TestCase):
    def test_vendor_dlkm_update_preserves_other_bytes_and_is_a_noop_when_equal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "disk.img"
            image.write_bytes(b"D" * 8192)
            names = ("system_a", "vendor_a", "system_ext_a", "vendor_dlkm_a")
            for name in (*names, "vbmeta_a"):
                (root / f"{name}.img").write_bytes(name.encode())
            table = {"partitiontable": {"label": "gpt", "sectorsize": 512, "partitions": [
                {"name": "super", "start": 1, "size": 6},
                {"name": "vbmeta_a", "start": 8, "size": 1},
            ]}}
            logical = [Partition(name, "group", [Extent(1, LP_TARGET_TYPE_LINEAR, index, 0)])
                       for index, name in enumerate(names)]
            with patch("android_sync.subprocess.check_output", return_value=json.dumps(table).encode()), \
                    patch("android_sync.read_partitions", return_value=logical):
                sync(image, root)
                data = image.read_bytes()
                self.assertEqual(data[2048:2048 + len("vendor_dlkm_a")], b"vendor_dlkm_a")
                self.assertEqual(data[:512], b"D" * 512)
                self.assertEqual(data[2560:4096], b"D" * 1536)
                self.assertEqual(data[4608:], b"D" * 3584)
                before = image.stat().st_mtime_ns
                sync(image, root)
                self.assertEqual(image.stat().st_mtime_ns, before)
                self.assertEqual(image.read_bytes(), data)
                (root / "system_a.img").write_bytes(b"would otherwise be updated")
                (root / "vendor_dlkm_a.img").write_bytes(b"oversized" * 100)
                with self.assertRaisesRegex(ValueError, "does not fit vendor_dlkm_a"):
                    sync(image, root)
                self.assertEqual(image.stat().st_mtime_ns, before)
                self.assertEqual(image.read_bytes(), data)

    def test_scanout_rejects_qemu_inactive_placeholder_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "screen.png"
            prefix = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
            path.write_bytes(prefix + struct.pack(">II", 640, 480))
            with self.assertRaisesRegex(RuntimeError, "not the requested"):
                check_scanout(path)
            path.write_bytes(prefix + struct.pack(">II", 1280, 720))
            check_scanout(path)

    def test_scanout_rejects_missing_png_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "screen.png"
            path.write_bytes(b"not a screenshot")
            with self.assertRaisesRegex(RuntimeError, "PNG scanout"):
                check_scanout(path)

    def test_extent_copy_preserves_data_outside_os_partition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "disk"
            source = root / "component"
            image.write_bytes(b"D" * 128)
            source.write_bytes(b"new filesystem")
            extents = [(16, 8), (40, 16)]
            with image.open("r+b") as disk:
                copy_component(disk, source, extents)
                self.assertEqual(disk_hash(disk, extents, source.stat().st_size),
                                 hashlib.sha256(source.read_bytes()).hexdigest())
            content = image.read_bytes()
            self.assertEqual(content[:16], b"D" * 16)
            self.assertEqual(content[24:40], b"D" * 16)
            self.assertEqual(content[56:], b"D" * 72)
            self.assertEqual(content[46:56], bytes(10))

    def test_raw_device_and_symlink_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "regular disk image"):
            sync(Path("/dev/null"), Path("/does-not-exist"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "disk").touch()
            (root / "link").symlink_to(root / "disk")
            with self.assertRaises(ValueError):
                sync(root / "link", root)

    def test_updates_refuse_a_running_vm_without_touching_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "disk.img"
            image.write_bytes(b"preserve Android data")
            with (root / "disk.img.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, "Stop QEMU"):
                    sync(image, root)
            self.assertEqual(image.read_bytes(), b"preserve Android data")


if __name__ == "__main__":
    unittest.main()
