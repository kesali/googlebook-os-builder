import fcntl
import hashlib
from pathlib import Path
import sys
import struct
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from android_overlay import properties, remove_hals
from android_sync import copy_component, disk_hash, sync
from android_smoke import check_scanout
from qemu_modules import main as add_qemu_modules


class AndroidTests(unittest.TestCase):
    def test_first_stage_module_lists_have_no_empty_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            modules = root / "modules"
            version = modules / "lib/modules/test-kernel"
            version.mkdir(parents=True)
            (version / "virtio_dma_buf.ko").touch()
            (version / "virtio-gpu.ko").touch()
            (version / "modules.dep").write_text("virtio_dma_buf.ko:\nvirtio-gpu.ko: virtio_dma_buf.ko\n")
            destination = root / "ramdisk"
            destination.mkdir()
            (destination / "modules.dep").write_text("/lib/modules/original.ko:\n")
            (destination / "modules.load").write_text("original.ko\n")
            outputs = [f"insmod {version}/virtio_dma_buf.ko\ninsmod {version}/virtio-gpu.ko\n", "", ""]
            with patch("sys.argv", ["qemu_modules.py", str(modules), str(destination)]), \
                    patch("qemu_modules.subprocess.check_output", side_effect=outputs):
                add_qemu_modules()
            self.assertEqual((destination / "modules.dep").read_text(),
                             "/lib/modules/original.ko:\n/lib/modules/virtio_dma_buf.ko:\n"
                             "/lib/modules/virtio-gpu.ko: /lib/modules/virtio_dma_buf.ko\n")
            self.assertEqual((destination / "modules.load").read_text(),
                             "original.ko\nvirtio_dma_buf.ko\nvirtio-gpu.ko\n")

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

    def test_properties_replace_in_place_and_keep_unrelated_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "build.prop"
            path.write_text("ro.hardware.egl=angle\nkeep=value\nro.hardware.egl=duplicate\n")
            inode = path.stat().st_ino
            changes = root / "changes"
            changes.write_text("# software graphics\nro.hardware.egl=mesa\n")
            properties(path, changes)
            self.assertEqual(path.read_text(), "keep=value\nro.hardware.egl=mesa\n")
            self.assertEqual(path.stat().st_ino, inode)

    def test_vintf_removes_only_selected_hals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.xml"
            path.write_text('<manifest version="9.0"><hal><name>vm</name></hal>'
                            '<hal><name>keep</name></hal></manifest>')
            remove_hals(path, {"vm"})
            self.assertNotIn("<name>vm</name>", path.read_text())
            self.assertIn("<name>keep</name>", path.read_text())


if __name__ == "__main__":
    unittest.main()
