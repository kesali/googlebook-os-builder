"""UEFI test safety and evidence checks, using fake inputs only."""

import fcntl
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from android_uefi_test import check_storage, copy_disk, qemu_command, serial_menu


class AndroidUefiTests(unittest.TestCase):
    def test_only_the_linux_entry_gets_a_serial_console(self):
        menu = "# linux and initcall_blacklist=nvme_init\nlinux kernel console=drm_log initcall_blacklist=nvme_init\ninitrd ramdisk\n"
        self.assertEqual(serial_menu(menu), menu.replace("\ninitrd", " console=ttyS1,115200\ninitrd"))

    def test_ambiguous_or_unsafe_menus_are_rejected(self):
        for menu in (
            "# initcall_blacklist=nvme_init\nlinux kernel\n",
            "linux kernel initcall_blacklist=nvme_init\nlinux other\n",
            "linux kernel initcall_blacklist=nvme_init console=tty0\n",
            "linux kernel initcall_blacklist=nvme_init\n",
            "initrd ramdisk\n",
        ):
            with self.subTest(menu=menu), self.assertRaises(ValueError):
                serial_menu(menu)

    def test_repository_menu_explicitly_enables_drm_log(self):
        menu = Path(__file__).resolve().parents[1] / "boot/android-menu.cfg"
        self.assertIn("console=drm_log", serial_menu(menu.read_text()))

    def test_copy_leaves_original_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            image = work / "disk.img"
            image.write_bytes(b"Android data")
            before = image.stat().st_mtime_ns
            copy_disk(image, work / "copy.img")
            (work / "copy.img").write_bytes(b"guest changes")
            self.assertEqual(image.read_bytes(), b"Android data")
            self.assertEqual(image.stat().st_mtime_ns, before)

    def test_copy_refuses_symlinks_directories_and_an_in_use_disk(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            image = work / "disk.img"
            image.write_bytes(b"Android data")
            link = work / "link"
            link.symlink_to(image)
            for source in (link, work, Path("/dev/null")):
                with self.subTest(source=source), self.assertRaisesRegex(ValueError, "regular disk image"):
                    copy_disk(source, work / "copy.img")
            with Path(str(image) + ".lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, "Stop QEMU"):
                    copy_disk(image, work / "copy.img")
            self.assertFalse((work / "copy.img").exists())

    def evidence(self):
        return {
            "kernel": "[drm] Initialized simpledrm\nprintk: console [drm_log0] enabled\n",
            "cmdline": "root=/dev/ram0 initcall_blacklist=nvme_init console=ttyS1,115200\n",
            "blocks": "dm-0\nsda\nsda12\n",
            "controllers": "",
            "boot_path": "/sys/devices/pci0000:00/0000:00:02.0/usb1/1-1/host0/target0:0:0/0:0:0:0/block/sda/sda12\n",
        }

    def test_usb_boot_with_hidden_nvme_passes(self):
        check_storage(**self.evidence())

    def test_nvme_enumeration_is_caught_even_if_later_removed(self):
        for field, value in (("kernel", "nvme nvme0: pci function 0000:00:03.0"),
                             ("blocks", "nvme0n1\n"), ("controllers", "nvme0\n")):
            evidence = self.evidence()
            evidence[field] += value
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "enumerated"):
                check_storage(**evidence)

    def test_missing_blacklist_usb_path_or_drm_log_is_rejected(self):
        for field, value in (("cmdline", "root=/dev/ram0"), ("boot_path", "/sys/block/sda/sda12"),
                             ("kernel", "[drm] Initialized simpledrm\n")):
            evidence = self.evidence()
            evidence[field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                check_storage(**evidence)

    def test_graphical_run_requires_no_firmware_framebuffer_and_nvme_hidden(self):
        evidence = self.evidence()
        with self.assertRaisesRegex(RuntimeError, "firmware framebuffer"):
            check_storage(**evidence, graphical=True)
        evidence["kernel"] = "[drm] Initialized virtio_gpu"
        check_storage(**evidence, graphical=True)
        evidence["cmdline"] = "initcall_blacklist=sysfb_init"
        with self.assertRaisesRegex(RuntimeError, "blacklist"):
            check_storage(**evidence, graphical=True)

    def test_qemu_boots_firmware_not_direct_kernel_and_has_writable_decoy(self):
        invocation = qemu_command(Path("/work"), Path("/logs"), "4", "6G", graphical=True)
        self.assertNotIn("-kernel", invocation)
        self.assertNotIn("-initrd", invocation)
        self.assertNotIn("-append", invocation)
        self.assertIn("nvme,id=decoy,drive=internal,serial=GBOS-BUILDER-DECOY,addr=3", invocation)
        self.assertIn("virtio-gpu-pci,addr=2,xres=1280,yres=720", invocation)
        self.assertIn("if=none,id=internal,format=raw,file=/work/nvme.img", invocation)
        self.assertIn("usb-storage,bus=xhci.0,drive=stick,bootindex=1", invocation)
        console = qemu_command(Path("/work"), Path("/logs"), "4", "6G", graphical=False)
        self.assertIn("virtio-vga,addr=2,xres=1280,yres=720", console)


if __name__ == "__main__":
    unittest.main()
