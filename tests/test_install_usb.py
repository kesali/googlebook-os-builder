"""Test owner-run fresh flashing on regular files, never devices or mounts."""

from contextlib import ExitStack
import fcntl
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import install_usb


class InstallUSBTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.image = self.root / "image"
        self.target = self.root / "target"
        self.image.write_bytes(b"I" * 4096)
        self.target.write_bytes(b"T" * 8192)
        self.node = {"name": str(self.target), "serial": "TEST123", "size": 8192,
                     "model": "Test USB", "ro": False, "maj:min": "8:0"}
        self.expected = hashlib.sha256(self.image.read_bytes()).hexdigest()

    def test_full_write_and_readback_leave_trailing_space_unchanged(self):
        guard, flush = Mock(), Mock()
        with self.image.open("rb") as source, self.target.open("r+b") as target:
            install_usb.flash(source, target, 4096, self.expected, guard, flush)
        self.assertEqual(self.target.read_bytes(), b"I" * 4096 + b"T" * 4096)
        self.assertEqual(self.image.read_bytes(), b"I" * 4096)
        self.assertEqual(guard.call_count, 2)
        flush.assert_called_once()

    def test_source_truncation_and_changed_hash_fail_loudly(self):
        for size, digest, message in ((8192, self.expected, "ended"),
                                      (4096, "wrong", "changed")):
            with self.subTest(size=size), self.image.open("rb") as source, \
                    self.target.open("r+b") as target, self.assertRaisesRegex(ValueError, message):
                install_usb.flash(source, target, size, digest, Mock(), Mock())

    def test_readback_corruption_is_rejected(self):
        def corrupt():
            with self.target.open("r+b") as stream:
                stream.write(b"X")
        with self.image.open("rb") as source, self.target.open("r+b") as target, \
                self.assertRaisesRegex(OSError, "read-back differs"):
            install_usb.flash(source, target, 4096, self.expected, Mock(), corrupt)

    def test_short_write_is_rejected(self):
        with self.image.open("rb") as source, self.assertRaisesRegex(OSError, "Short write"):
            install_usb.flash(source, Mock(write=Mock(return_value=0)),
                              4096, self.expected, Mock(), Mock())

    def test_capacity_readonly_and_missing_serial_are_rejected(self):
        for changed in ({"size": 2048}, {"ro": True}, {"serial": ""}, {"serial": " "}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                install_usb.check_capacity({**self.node, **changed}, 4096)

    def run_install(self, answer, selected=True, identity_error=False, sector_size=512,
                    busy=False, changed_source=False):
        with ExitStack() as patches:
            patches.enter_context(patch("install_usb.os.geteuid", return_value=0))
            patches.enter_context(patch("install_usb.shutil.which", return_value="/command"))
            patches.enter_context(patch("install_usb.table", return_value={
                "partitions": [{"name": name} for name in ("userdata", "metadata", "EFI-SYSTEM")]}))
            verify = patches.enter_context(patch("install_usb.subprocess.run"))
            verify.return_value = subprocess.CompletedProcess([], 0, "", "")
            target_verify = patches.enter_context(patch("install_usb.verify_target_gpt"))
            patches.enter_context(patch("install_usb.os_extents"))
            patches.enter_context(patch("install_usb.choose",
                                        return_value=self.node if selected else None))
            unused = patches.enter_context(patch("install_usb.check_unused"))
            if busy:
                unused.side_effect = ValueError("USB is mounted")
            patches.enter_context(patch("install_usb.stat.S_ISBLK", return_value=True))
            identity = patches.enter_context(patch("install_usb.check_identity",
                                                   return_value=self.node))
            if identity_error:
                identity.side_effect = ValueError("USB changed")
            patches.enter_context(patch("install_usb.fcntl.ioctl",
                                        return_value=sector_size.to_bytes(4, "little")))
            prompt = patches.enter_context(patch("builtins.input", return_value=answer))
            if changed_source:
                def change_source(_):
                    self.image.write_bytes(b"changed" * 1024)
                    return answer
                prompt.side_effect = change_source
            before = self.target.read_bytes()
            if identity_error or sector_size != 512 or busy or changed_source:
                with self.assertRaises(ValueError):
                    install_usb.install(self.image)
                self.assertEqual(self.target.read_bytes(), before)
                if not changed_source:
                    prompt.assert_not_called()
            else:
                install_usb.install(self.image)
                if answer == "ERASE TEST123" and selected:
                    self.assertEqual(self.target.read_bytes(), b"I" * 4096 + b"T" * 4096)
                    self.assertEqual(verify.call_count, 1)
                    target_verify.assert_called_once()
                    self.assertGreaterEqual(identity.call_count, 4)
                else:
                    self.assertEqual(self.target.read_bytes(), before)
                    self.assertEqual(verify.call_count, 1)
                    target_verify.assert_not_called()
                    if not selected:
                        prompt.assert_not_called()

    def test_exact_serial_confirmation_is_required(self):
        for answer in ("", "yes", "ERASE", "ERASE OTHER", "erase TEST123"):
            with self.subTest(answer=answer):
                self.run_install(answer)
        self.run_install("ERASE TEST123")

    def test_cancelled_selection_writes_nothing(self):
        self.run_install("", selected=False)

    def test_changed_device_and_non512_sectors_refuse_before_prompt(self):
        self.run_install("ERASE TEST123", identity_error=True)
        self.run_install("ERASE TEST123", sector_size=4096)

    def test_mounted_target_refuses_before_confirmation(self):
        self.run_install("ERASE TEST123", busy=True)

    def test_changed_source_after_confirmation_refuses_before_writing(self):
        self.run_install("ERASE TEST123", changed_source=True)

    def test_busy_source_and_symlink_refuse_before_selection(self):
        with patch("install_usb.os.geteuid", return_value=0), \
                patch("install_usb.shutil.which", return_value="/command"), \
                patch("install_usb.choose") as choose:
            with Path(str(self.image) + ".lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    install_usb.install(self.image)
            link = self.root / "link"
            link.symlink_to(self.image)
            with self.assertRaisesRegex(ValueError, "regular built image"):
                install_usb.install(link)
            choose.assert_not_called()


if __name__ == "__main__":
    unittest.main()
