import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import deploy

REPO = Path(__file__).resolve().parents[1]
ANDROID_MENU = b"linux kernel-@KERNEL@ @CMDLINE@ panic=0\ninitrd initramfs-@INITRAMFS@\n"


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
        self.cmdline = self.root / "cmdline.txt"
        self.cmdline.write_text("# Logging\nlog_buf_len=1M\n\nroot=/dev/ram0  # the initrd\nbootconfig\n")
        self.android_menu = self.root / "android-menu.cfg"
        self.android_menu.write_bytes(ANDROID_MENU)
        self.bundle = self.root / "bundle"
        self.usb = self.root / "usb"
        self.usb.mkdir()
        self.publish()
        deploy.install(self.bundle, self.usb, initialize=True)

    def publish(self):
        deploy.bundle([self.inputs / name for name in deploy.COMPONENTS], self.bundle, "diagnostic")

    def publish_android(self):
        bundle = self.root / "android-bundle"
        inputs = [self.inputs / name for name in deploy.COMPONENTS[:3]] + [self.android_menu]
        deploy.bundle(inputs, bundle, "android", self.cmdline)
        return bundle

    def android_stage(self):
        stage = self.root / "android-stage"
        stage.mkdir()
        deploy.install(self.publish_android(), stage, initialize=True)
        return stage

    def snapshot(self, root=None):
        root = root or self.usb
        return {
            str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in root.rglob("*") if path.is_file()
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

    def test_android_menu_gets_the_command_line_on_one_line_and_the_android_marker(self):
        stage = self.android_stage()
        self.assertEqual((stage / "dali/format").read_bytes(), b"gbos-dali-android-v1\n")
        kernel = next((stage / "dali").glob("kernel-*")).name
        initramfs = next((stage / "dali").glob("initramfs-*")).name
        self.assertEqual(
            (stage / "dali/grub.cfg").read_text(),
            f"linux {kernel} log_buf_len=1M root=/dev/ram0 bootconfig panic=0\ninitrd {initramfs}\n",
        )

    def test_a_new_command_line_rewrites_only_the_menu(self):
        stage = self.android_stage()
        self.cmdline.write_text("root=/dev/ram0\n")
        self.assertEqual(deploy.install(self.publish_android(), stage), ["dali/grub.cfg"])

    def test_a_bundle_installs_only_onto_its_own_kind(self):
        # The marker of the already flashed diagnostic USB must stay what it was.
        self.assertEqual((self.usb / "dali/format").read_bytes(), b"gbos-dali-diagnostic-v1\n")
        stage = self.android_stage()
        usb_before, stage_before = self.snapshot(), self.snapshot(stage)
        with self.assertRaisesRegex(ValueError, "Not a Dali android"):
            deploy.install(self.publish_android(), self.usb)
        with self.assertRaisesRegex(ValueError, "Not a Dali diagnostic"):
            deploy.install(self.bundle, stage)
        self.assertEqual(usb_before, self.snapshot())
        self.assertEqual(stage_before, self.snapshot(stage))

    def test_menu_and_command_line_come_together_and_nothing_is_written_otherwise(self):
        diagnostic_inputs = [self.inputs / name for name in deploy.COMPONENTS]
        android_inputs = [*diagnostic_inputs[:3], self.android_menu]
        cases = [
            ("a command line for a menu without @CMDLINE@", diagnostic_inputs, self.cmdline, "no @CMDLINE@"),
            ("a menu with @CMDLINE@ and no command line", android_inputs, None, "no kernel command line"),
        ]
        for name, inputs, cmdline, message in cases:
            with self.subTest(name):
                destination = self.root / "never-written"
                with self.assertRaisesRegex(ValueError, message):
                    deploy.bundle(inputs, destination, "android", cmdline)
                self.assertFalse(destination.exists())

    def test_command_line_is_flattened_and_cannot_need_grub_quoting(self):
        self.assertEqual(deploy.flatten_cmdline("# note\n a=1  b # inline\n\nc=/x,y:z@w^v\n"), "a=1 b c=/x,y:z@w^v")
        for argument in ("a;b", "x=$y", "'q'", "a|b", 'say="hi"', "a{b}", "a*"):
            with self.subTest(argument):
                with self.assertRaisesRegex(ValueError, "GRUB quoting"):
                    deploy.flatten_cmdline(f"ok=1\n{argument}\n")

    def test_unknown_kind_is_rejected_when_bundling_and_installing(self):
        with self.assertRaisesRegex(ValueError, "Unknown bundle kind"):
            deploy.bundle([self.inputs / name for name in deploy.COMPONENTS], self.root / "x", "recovery")
        manifest = json.loads((self.bundle / "manifest.json").read_text())
        manifest["kind"] = "recovery"
        (self.bundle / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "Invalid build bundle manifest"):
            deploy.install(self.bundle, self.usb)

    def test_the_repository_android_menu_and_command_line_make_a_bundle(self):
        inputs = [*(self.inputs / name for name in deploy.COMPONENTS[:3]), REPO / "boot/android-menu.cfg"]
        bundle = self.root / "real-bundle"
        deploy.bundle(inputs, bundle, "android", REPO / "android/cmdline.txt")
        menu = (bundle / "menu.cfg").read_text()
        self.assertNotIn("@CMDLINE@", menu)
        linux_lines = [line for line in menu.splitlines() if line.lstrip().startswith("linux ")]
        self.assertEqual(len(linux_lines), 1)
        kernel_arguments = linux_lines[0].split()
        self.assertIn("root=/dev/ram0", kernel_arguments)
        # Android must never probe the internal NVMe, which holds another system.
        self.assertIn("initcall_blacklist=nvme_init", kernel_arguments)
        self.assertEqual(
            [argument for argument in kernel_arguments if argument.startswith("efi_pstore.pstore_disable=")],
            ["efi_pstore.pstore_disable=1"],
        )
        self.assertEqual(kernel_arguments[-1], "$1")
        self.assertNotIn("initcall_blacklist=sysfb_init", kernel_arguments)
        normal_entry = 'menuentry "Googlebook OS" {\n    boot_android\n}'
        test_entry = (
            'menuentry "Googlebook OS (test: no firmware framebuffer)" {\n'
            '    boot_android initcall_blacklist=sysfb_init\n}'
        )
        self.assertIn("set default=0\n", menu)
        self.assertIn(normal_entry, menu)
        self.assertIn(test_entry, menu)
        self.assertLess(menu.index(normal_entry), menu.index(test_entry))
        self.assertIn(
            'menuentry "Previous build (may write UEFI crash records)" {\n'
            '        configfile ($root)/dali/grub.previous.cfg\n    }',
            menu,
        )

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
