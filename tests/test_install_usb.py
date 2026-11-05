"""Test owner-run fresh flashing on regular files, never devices or mounts."""

from contextlib import ExitStack
import copy
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
            patches.enter_context(patch("install_usb.os_extents"))
            patches.enter_context(patch("install_usb.data_layout"))
            initialize = patches.enter_context(patch("install_usb.initialize_data"))
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
                    initialize.assert_called_once()
                    self.assertGreaterEqual(identity.call_count, 4)
                else:
                    self.assertEqual(self.target.read_bytes(), before)
                    self.assertEqual(verify.call_count, 1)
                    initialize.assert_not_called()
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


class FreshDataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source.img"
        self.target = self.root / "usb.img"
        self.source_size = 32 << 20
        self.target_size = 64 << 20
        with self.source.open("wb") as stream:
            stream.truncate(self.source_size)
        lines = ["label: gpt"]
        for name in install_usb.PARTITIONS:
            size = 4 if name == "userdata" else 1
            lines.append(f'size={size * 2048}, type=L, name="{name}"')
        subprocess.run(["sfdisk", "--quiet", str(self.source)],
                       input="\n".join(lines) + "\n", text=True, capture_output=True, check=True)
        self.table = install_usb.table(self.source)
        with self.source.open("r+b") as stream:
            for part in self.table["partitions"]:
                stream.seek(part["start"] * 512)
                stream.write(part["name"].encode().ljust(part["size"] * 512, b"X"))
        with self.source.open("rb") as source, self.target.open("wb") as target:
            target.write(source.read())
            target.truncate(self.target_size)

    def test_expansion_preserves_os_and_ids_and_resets_only_fresh_android_state(self):
        source_before = self.source.read_bytes()
        before = self.target.read_bytes()
        guard, flush = Mock(), Mock()
        with self.target.open("r+b", buffering=0) as target:
            install_usb.initialize_data(self.table, self.source_size, target,
                                        self.target_size, guard, flush)
        grown = install_usb.table(self.target)
        install_usb.check_layout(self.table, grown)
        data = grown["partitions"][-1]
        self.assertEqual(data["start"] + data["size"], grown["lastlba"] + 1)
        self.assertGreater(data["size"], self.table["partitions"][-1]["size"])
        after = self.target.read_bytes()
        for part in self.table["partitions"]:
            start = part["start"] * 512
            end = start + part["size"] * 512
            with self.subTest(name=part["name"]):
                if part["name"] == "metadata":
                    self.assertEqual(after[start:end], bytes(end - start))
                elif part["name"] == "userdata":
                    self.assertEqual(after[start:start + (1 << 20)], bytes(1 << 20))
                    self.assertEqual(after[start + (1 << 20):end], before[start + (1 << 20):end])
                else:
                    self.assertEqual(after[start:end], before[start:end])
        self.assertEqual(self.source.read_bytes(), source_before)
        self.assertGreaterEqual(guard.call_count, 5)
        self.assertGreaterEqual(flush.call_count, 3)

    def test_bad_layouts_refuse_before_any_target_write(self):
        cases = []
        missing = copy.deepcopy(self.table)
        missing["partitions"].pop(0)
        cases.append((missing, self.target_size))
        moved = copy.deepcopy(self.table)
        moved["partitions"][-1]["start"] = 1
        cases.append((moved, self.target_size))
        oversized = copy.deepcopy(self.table)
        oversized["partitions"][-1]["size"] = self.source_size
        cases.append((oversized, self.target_size))
        bad_backup = copy.deepcopy(self.table)
        bad_backup["lastlba"] = self.source_size // 512
        cases.append((bad_backup, self.target_size))
        bad_number = copy.deepcopy(self.table)
        bad_number["partitions"][-1]["node"] = "/dev/fake99"
        cases.append((bad_number, self.target_size))
        cases.extend([(self.table, self.source_size - 512), (self.table, self.target_size + 1)])
        before = self.target.read_bytes()
        for table, size in cases:
            with self.subTest(table=table, size=size), self.target.open("r+b") as target:
                guard = Mock()
                with self.assertRaises(ValueError):
                    install_usb.initialize_data(table, self.source_size, target, size, guard, Mock())
                guard.assert_not_called()
                self.assertEqual(self.target.read_bytes(), before)

    def test_same_capacity_install_still_initializes_data_and_verifies_gpt(self):
        with self.target.open("r+b") as target:
            target.truncate(self.source_size)
            install_usb.initialize_data(self.table, self.source_size, target,
                                        self.source_size, Mock(), Mock())
        install_usb.check_layout(self.table, install_usb.table(self.target))

    def test_guard_failure_prevents_reset_or_gpt_changes(self):
        before = self.target.read_bytes()
        with self.target.open("r+b") as target, self.assertRaisesRegex(ValueError, "changed"):
            install_usb.initialize_data(self.table, self.source_size, target, self.target_size,
                                        Mock(side_effect=ValueError("USB changed")), Mock())
        self.assertEqual(self.target.read_bytes(), before)

    def test_data_reset_corruption_is_reported(self):
        def corrupt():
            metadata = next(p for p in self.table["partitions"] if p["name"] == "metadata")
            with self.target.open("r+b") as stream:
                stream.seek(metadata["start"] * 512)
                stream.write(b"bad")
        with self.target.open("r+b", buffering=0) as target, \
                self.assertRaisesRegex(OSError, "Read-back differs"):
            install_usb.initialize_data(self.table, self.source_size, target, self.target_size,
                                        Mock(), corrupt)

    def test_short_reset_write_is_reported(self):
        target = Mock(write=Mock(return_value=0))
        with self.assertRaisesRegex(OSError, "Short write resetting metadata"):
            install_usb.initialize_data(self.table, self.source_size, target,
                                        self.target_size, Mock(), Mock())

    def test_gpt_tool_failure_is_reported(self):
        with self.target.open("r+b", buffering=0) as target, \
                patch("install_usb.subprocess.run",
                      side_effect=subprocess.CalledProcessError(1, ["sfdisk"])), \
                self.assertRaises(subprocess.CalledProcessError):
            install_usb.initialize_data(self.table, self.source_size, target,
                                        self.target_size, Mock(), Mock())


if __name__ == "__main__":
    unittest.main()
