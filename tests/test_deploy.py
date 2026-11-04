import json
from pathlib import Path
import subprocess
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
        inputs = [self.inputs / name for name in deploy.COMPONENTS[:3]] + [self.android_menu]
        deploy.bundle(inputs, self.bundle, "android", self.cmdline)

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
        self.assertTrue(changed[0].startswith("gbos-builder/initramfs-"))
        self.assertEqual(changed[1], "gbos-builder/grub.cfg")
        after = self.snapshot()
        for name, original in before.items():
            if name != "gbos-builder/grub.cfg":
                self.assertEqual(after[name], original, name)
        self.assertEqual(after["gbos-builder/grub.previous.cfg"][0], before["gbos-builder/grub.cfg"][0])

    def test_kernel_only_update_does_not_rewrite_initramfs(self):
        (self.inputs / "kernel").write_bytes(b"new source-built kernel")
        self.publish()
        changed = deploy.install(self.bundle, self.usb)
        self.assertEqual(len(changed), 2)
        self.assertTrue(changed[0].startswith("gbos-builder/kernel-"))
        self.assertEqual(changed[1], "gbos-builder/grub.cfg")

    def test_corrupt_destination_is_repaired_without_trusting_a_manifest(self):
        kernel = next((self.usb / "gbos-builder").glob("kernel-*"))
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
        (self.usb / "gbos-builder/format").unlink()
        with self.assertRaisesRegex(ValueError, "Not a gbos-builder"):
            deploy.install(self.bundle, self.usb)
        self.assertEqual(len(self.snapshot()), len(before) - 1)

    def test_legacy_marker_is_rejected_without_writes(self):
        (self.usb / "gbos-builder/format").write_bytes(b"gbos-dali-diagnostic-v1\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Not a gbos-builder"):
            deploy.install(self.bundle, self.usb)
        self.assertEqual(before, self.snapshot())

    def test_legacy_directory_is_rejected_without_writes(self):
        (self.usb / "gbos-builder/format").write_bytes(b"gbos-dali-diagnostic-v1\n")
        (self.usb / "gbos-builder").rename(self.usb / "dali")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Not a gbos-builder"):
            deploy.install(self.bundle, self.usb)
        self.assertEqual(before, self.snapshot())

    def test_marker_uses_the_project_identity(self):
        self.assertEqual(deploy.FORMATS, {"android": b"gbos-builder-android-v1\n"})

    def test_android_menu_gets_the_command_line_on_one_line_and_the_android_marker(self):
        stage = self.usb
        self.assertEqual((stage / "gbos-builder/format").read_bytes(), b"gbos-builder-android-v1\n")
        self.assertTrue(deploy.valid_grubenv((stage / "grubenv").read_bytes()))
        env = subprocess.run(
            ["grub-editenv", str(stage / "grubenv"), "list"],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertIn("saved_entry=android-berberis\n", env)
        kernel = next((stage / "gbos-builder").glob("kernel-*")).name
        initramfs = next((stage / "gbos-builder").glob("initramfs-*")).name
        self.assertEqual(
            (stage / "gbos-builder/grub.cfg").read_text(),
            f"linux {kernel} log_buf_len=1M root=/dev/ram0 bootconfig panic=0\ninitrd {initramfs}\n",
        )

    def test_android_update_preserves_saved_entry_and_initializes_it_if_missing(self):
        grubenv = self.usb / "grubenv"
        subprocess.run(["grub-editenv", str(grubenv), "set", "saved_entry=android-houdini"], check=True)
        saved = grubenv.read_bytes()

        (self.inputs / "kernel").write_bytes(b"updated kernel")
        self.publish()
        self.assertEqual(deploy.install(self.bundle, self.usb)[-1], "gbos-builder/grub.cfg")
        self.assertEqual(grubenv.read_bytes(), saved)

        grubenv.unlink()
        dry_run = deploy.install(self.bundle, self.usb, dry_run=True)
        self.assertIn("grubenv", dry_run)
        self.assertIn("grubenv", deploy.install(self.bundle, self.usb))
        env = subprocess.run(
            ["grub-editenv", str(grubenv), "list"],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertIn("saved_entry=android-berberis\n", env)

    def test_android_update_refuses_invalid_grubenv_without_replacing_it(self):
        grubenv = self.usb / "grubenv"
        grubenv.write_bytes(b"broken saved selection")
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            deploy.install(self.bundle, self.usb)
        self.assertEqual(grubenv.read_bytes(), b"broken saved selection")

    def test_a_new_command_line_rewrites_only_the_menu(self):
        self.cmdline.write_text("root=/dev/ram0\n")
        self.publish()
        self.assertEqual(deploy.install(self.bundle, self.usb), ["gbos-builder/grub.cfg"])

    def test_retired_diagnostic_usb_is_rejected_without_writes(self):
        # A stick flashed with the removed diagnostic OS must never receive Android files.
        (self.usb / "gbos-builder/format").write_bytes(b"gbos-builder-diagnostic-v1\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Not a gbos-builder android"):
            deploy.install(self.bundle, self.usb)
        self.assertEqual(before, self.snapshot())

    def test_menu_and_command_line_come_together_and_nothing_is_written_otherwise(self):
        plain_menu_inputs = [self.inputs / name for name in deploy.COMPONENTS]
        android_inputs = [*plain_menu_inputs[:3], self.android_menu]
        cases = [
            ("a command line for a menu without @CMDLINE@", plain_menu_inputs, self.cmdline, "no @CMDLINE@"),
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
        for kind in ("recovery", "diagnostic"):
            with self.subTest(kind), self.assertRaisesRegex(ValueError, "Unknown bundle kind"):
                deploy.bundle([self.inputs / name for name in deploy.COMPONENTS], self.root / "x", kind)
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
        # Churro's MT7922 workaround: the CLC download panicked this laptop.
        self.assertIn("mt7921_common.disable_clc=1", kernel_arguments)
        self.assertEqual(
            [argument for argument in kernel_arguments if argument.startswith("efi_pstore.pstore_disable=")],
            ["efi_pstore.pstore_disable=1"],
        )
        self.assertEqual(kernel_arguments[-1], "$1")
        self.assertNotIn("initcall_blacklist=sysfb_init", kernel_arguments)
        # The firmware console drew each early line synchronously: 60 s of the laptop's boot.
        self.assertNotIn("earlycon=efifb", kernel_arguments)
        berberis_entry = 'menuentry "Googlebook OS (Berberis)" --id=android-berberis'
        houdini_entry = 'menuentry "Googlebook OS (Houdini)" --id=android-houdini'
        test_entry = (
            'menuentry "Googlebook OS (test: no firmware framebuffer)" {\n'
            '    boot_android initcall_blacklist=sysfb_init\n}'
        )
        debug_entry = (
            'menuentry "Googlebook OS (debug: slow early screen log, for black screens)" {\n'
            '    boot_android earlycon=efifb\n}'
        )
        self.assertIn("set default=android-berberis\n", menu)
        self.assertIn(berberis_entry, menu)
        self.assertIn(houdini_entry, menu)
        self.assertIn(test_entry, menu)
        self.assertIn(debug_entry, menu)
        self.assertLess(menu.index(berberis_entry), menu.index(test_entry))
        self.assertLess(menu.index(houdini_entry), menu.index(test_entry))
        self.assertLess(menu.index(berberis_entry), menu.index(debug_entry))
        self.assertIn(
            'menuentry "Previous build (may write UEFI crash records)" {\n'
            '        configfile ($root)/gbos-builder/grub.previous.cfg\n    }',
            menu,
        )

    def test_symlink_is_rejected_before_writes(self):
        (self.usb / "gbos-builder/grub.previous.cfg").symlink_to(self.inputs / "kernel")
        with self.assertRaisesRegex(ValueError, "symlink"):
            deploy.install(self.bundle, self.usb)
        self.assertEqual((self.inputs / "kernel").read_bytes(), b"kernel")

    def test_failed_payload_write_does_not_switch_menu(self):
        old_menu = (self.usb / "gbos-builder/grub.cfg").read_bytes()
        (self.inputs / "kernel").write_bytes(b"new kernel")
        (self.inputs / "initramfs.gz").write_bytes(b"new ramdisk")
        self.publish()
        replace = deploy.replace_file

        def interrupted(root, name, data):
            if name.startswith("gbos-builder/initramfs-"):
                raise OSError("simulated unplug")
            return replace(root, name, data)

        with patch.object(deploy, "replace_file", side_effect=interrupted):
            with self.assertRaisesRegex(OSError, "simulated unplug"):
                deploy.install(self.bundle, self.usb)
        self.assertEqual((self.usb / "gbos-builder/grub.cfg").read_bytes(), old_menu)
        deploy.install(self.bundle, self.usb)
        self.assertNotEqual((self.usb / "gbos-builder/grub.cfg").read_bytes(), old_menu)


if __name__ == "__main__":
    unittest.main()
