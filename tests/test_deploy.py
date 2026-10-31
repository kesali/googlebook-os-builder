import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import deploy


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        for name in deploy.COMPONENTS:
            (self.inputs / name).write_bytes(name.encode())
        (self.inputs / "menu.cfg").write_bytes(b"kernel=@KERNEL@ initramfs=@INITRAMFS@")
        self.bundle = self.root / "bundle"
        self.usb = self.root / "usb"
        self.usb.mkdir()
        self.publish()
        deploy.install(self.bundle, self.usb, initialize=True)

    def publish(self):
        deploy.bundle([self.inputs / name for name in deploy.COMPONENTS], self.bundle)

    def snapshot(self):
        return {
            str(path.relative_to(self.usb)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.usb.rglob("*") if path.is_file()
        }

    def test_noop_writes_nothing_even_with_full_disk(self):
        before = self.snapshot()
        with patch.object(deploy.os, "statvfs", side_effect=AssertionError("no space check needed")):
            self.assertEqual(deploy.install(self.bundle, self.usb), [])
        self.assertEqual(before, self.snapshot())

    def test_initramfs_update_preserves_kernel_loader_and_user_files(self):
        for name in ("userdata.img", "logs/keep.txt"):
            path = self.usb / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b"keep me")
        before = self.snapshot()
        (self.inputs / "initramfs.gz").write_bytes(b"edited init script")
        self.publish()
        changed = deploy.install(self.bundle, self.usb)
        self.assertEqual(len(changed), 2)
        self.assertTrue(changed[0].startswith("dali/initramfs-"))
        self.assertEqual(changed[1], "dali/grub.cfg")
        after = self.snapshot()
        for name, original in before.items():
            if name != "dali/grub.cfg":
                self.assertEqual(after[name], original, name)
        self.assertEqual(after["dali/grub.previous.cfg"][0], before["dali/grub.cfg"][0])

    def test_kernel_only_update_does_not_rewrite_initramfs(self):
        (self.inputs / "kernel").write_bytes(b"new source-built kernel")
        self.publish()
        changed = deploy.install(self.bundle, self.usb)
        self.assertEqual(len(changed), 2)
        self.assertTrue(changed[0].startswith("dali/kernel-"))
        self.assertEqual(changed[1], "dali/grub.cfg")

    def test_corrupt_destination_is_repaired_without_trusting_a_manifest(self):
        kernel = next((self.usb / "dali").glob("kernel-*"))
        kernel.write_bytes(b"broken")
        self.assertEqual(deploy.install(self.bundle, self.usb), [str(kernel.relative_to(self.usb))])
        self.assertEqual(kernel.read_bytes(), b"kernel")

    def test_bad_bundle_fails_before_any_write(self):
        before = self.snapshot()
        (self.bundle / "kernel").write_bytes(b"unverified")
        with self.assertRaisesRegex(ValueError, "checksum"):
            deploy.install(self.bundle, self.usb)
        self.assertEqual(before, self.snapshot())

    def test_unknown_destination_is_rejected(self):
        before = self.snapshot()
        (self.usb / "dali/format").unlink()
        with self.assertRaisesRegex(ValueError, "Not a Dali"):
            deploy.install(self.bundle, self.usb)
        self.assertEqual(len(self.snapshot()), len(before) - 1)

    def test_symlink_is_rejected_before_writes(self):
        (self.usb / "dali/grub.previous.cfg").symlink_to(self.inputs / "kernel")
        with self.assertRaisesRegex(ValueError, "symlink"):
            deploy.install(self.bundle, self.usb)
        self.assertEqual((self.inputs / "kernel").read_bytes(), b"kernel")

    def test_failed_payload_write_does_not_switch_menu(self):
        old_menu = (self.usb / "dali/grub.cfg").read_bytes()
        (self.inputs / "kernel").write_bytes(b"new kernel")
        (self.inputs / "initramfs.gz").write_bytes(b"new ramdisk")
        self.publish()
        replace = deploy.replace_file

        def interrupted(root, name, data):
            if name.startswith("dali/initramfs-"):
                raise OSError("simulated unplug")
            return replace(root, name, data)

        with patch.object(deploy, "replace_file", side_effect=interrupted):
            with self.assertRaisesRegex(OSError, "simulated unplug"):
                deploy.install(self.bundle, self.usb)
        self.assertEqual((self.usb / "dali/grub.cfg").read_bytes(), old_menu)
        deploy.install(self.bundle, self.usb)
        self.assertNotEqual((self.usb / "dali/grub.cfg").read_bytes(), old_menu)

    def test_mount_guard_rejects_root_symlinks_and_non_usb(self):
        with self.assertRaises(ValueError):
            deploy.verify_usb_mount(Path("/"))
        link = self.root / "link"
        link.symlink_to(self.usb)
        with self.assertRaises(ValueError):
            deploy.verify_usb_mount(link)
        mount = {"filesystems": [{
            "target": str(self.usb), "source": "/dev/null", "fstype": "vfat", "options": "rw",
        }]}
        disks = {"blockdevices": [{"type": "part", "children": [{"type": "disk", "tran": "nvme"}]}]}
        results = [type("Result", (), {"stdout": json.dumps(value)}) for value in (mount, disks)]
        with patch.object(deploy.subprocess, "run", side_effect=results), patch.object(deploy.stat, "S_ISBLK", return_value=True):
            with self.assertRaisesRegex(ValueError, "not on a USB"):
                deploy.verify_usb_mount(self.usb)


if __name__ == "__main__":
    unittest.main()
