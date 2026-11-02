"""Verify migration-copy refusal and preservation without physical disks."""

import fcntl
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from lp import Extent, Partition
from super_migrate_copy import (
    ACTIVE_NAMES, VENDOR_DLKM_BYTES, check_slot_a, compare_outside_super, migrate, output_path,
)


class MigrationCopyTests(unittest.TestCase):
    def test_requires_successful_a_and_inactive_b(self):
        physical = {name: {} for name in
                    ("super", "vbmeta_a", "vbmeta_b", "userdata", "metadata", "EFI-SYSTEM")}
        physical["vbmeta_a"]["attrs"] = "GUID:48,49,50,51,56"
        check_slot_a(physical)
        for name in ("vbmeta_a", "vbmeta_b"):
            changed = {key: dict(value) for key, value in physical.items()}
            changed[name]["attrs"] = "GUID:48"
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "successful slot A"):
                check_slot_a(changed)
        del physical["metadata"]
        with self.assertRaisesRegex(ValueError, "partition layout"):
            check_slot_a(physical)

    def test_rejects_existing_output_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            existing = root / "existing"
            existing.write_bytes(b"keep")
            link = root / "link"
            link.symlink_to(root / "missing")
            for destination in (existing, link):
                with self.subTest(), self.assertRaisesRegex(ValueError, "Refusing to replace"):
                    output_path(destination)
            self.assertEqual(existing.read_bytes(), b"keep")

    def test_rejects_outputs_outside_out_or_named_disk(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "disposable"):
                output_path(Path(temporary) / "copy.img")
        with patch.object(Path, "exists", return_value=False), \
                patch.object(Path, "is_symlink", return_value=False), \
                self.assertRaisesRegex(ValueError, "never disk.img"):
            output_path(Path(__file__).resolve().parents[1] / "out/android/disk.img")

    def test_compares_every_byte_outside_super(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            candidate = Path(temporary) / "candidate"
            source.write_bytes(b"GPTxxxuserdata")
            candidate.write_bytes(b"GPTyyyuserdata")
            compare_outside_super(source, candidate, 3, 6)
            for contents in (b"xPTyyyuserdata", b"GPTyyyuserdatx", b"GPTyyyuserdata!"):
                with self.subTest(contents=contents):
                    candidate.write_bytes(contents)
                    with self.assertRaisesRegex(ValueError, "differ"):
                        compare_outside_super(source, candidate, 3, 6)

    def test_busy_source_is_rejected_before_reading_or_copying(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.write_bytes(b"keep")
            destination = root / "copy.img"
            with Path(str(source) + ".lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch("super_migrate_copy.output_path"), \
                        self.assertRaisesRegex(ValueError, "Stop the VM"):
                    migrate(source, source, destination)
            self.assertFalse(destination.exists())
            self.assertEqual(source.read_bytes(), b"keep")

    def run_mock_migration(self, root, vendor_size=18096128, empty_b=False,
                           metadata_agrees=True):
        source = root / "source.img"
        source.write_bytes(b"keep" * 4096)
        destination = root / "copy.img"
        physical = [{"name": name, "start": 1, "size": 1} for name in
                    ("super", "vbmeta_a", "vbmeta_b", "userdata", "metadata", "EFI-SYSTEM")]
        physical[1]["attrs"] = "GUID:48,49,50,51,56"
        table = {"label": "gpt", "unit": "sectors", "sectorsize": 512,
                 "partitions": physical}
        partitions = []
        for name in sorted(ACTIVE_NAMES):
            size = vendor_size if name == "vendor_dlkm_a" else 512
            partitions.append(Partition(name, "group_a", [Extent(size // 512, 0, 1, 0)]))
            partitions.append(Partition(name[:-1] + "b", "group_b", [] if empty_b else [
                Extent(1, 0, 2, 0)]))
        with ExitStack() as patches:
            patches.enter_context(patch("super_migrate_copy.OUT", root))
            patches.enter_context(patch("super_migrate_copy.subprocess.check_output",
                                        return_value=json.dumps({"partitiontable": table})))
            run = patches.enter_context(patch("super_migrate_copy.subprocess.run"))
            patches.enter_context(patch("super_migrate_copy.layout", return_value=(
                partitions, (0, 0, 0, 64, 3, 4096), [], 4096, 0)))
            patches.enter_context(patch("super_migrate_copy.read_at",
                                        side_effect=[bytes(64)] * 2 + [b"x" * 64] if not
                                        metadata_agrees else None, return_value=bytes(64)))
            extraction = patches.enter_context(patch("super_migrate_copy.extract"))
            builder = patches.enter_context(patch("super_migrate_copy.build",
                                                  side_effect=ValueError("generation failed")))
            if vendor_size == VENDOR_DLKM_BYTES and empty_b:
                migrate(source, source, destination)
                extraction.assert_not_called()
                builder.assert_not_called()
                self.assertEqual(run.call_count, 1)  # only read-only GPT verification
            else:
                message = "metadata copies disagree" if not metadata_agrees else (
                    "original" if vendor_size != 18096128 else "generation failed")
                with self.assertRaisesRegex(ValueError, message):
                    migrate(source, source, destination)
                if message == "generation failed":
                    self.assertEqual({call.args[2].name for call in extraction.call_args_list},
                                     ACTIVE_NAMES)
                else:
                    extraction.assert_not_called()
                    builder.assert_not_called()
        self.assertFalse(destination.exists())
        self.assertEqual(source.read_bytes(), b"keep" * 4096)
        self.assertFalse(list(root.glob("copy.img.partial.*")))

    def test_generation_failure_preserves_source_and_cleans_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.run_mock_migration(Path(temporary))

    def test_divergent_source_metadata_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.run_mock_migration(Path(temporary), metadata_agrees=False)

    def test_unexpected_original_allocation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.run_mock_migration(Path(temporary), vendor_size=4096)

    def test_already_migrated_source_writes_no_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.run_mock_migration(Path(temporary), vendor_size=VENDOR_DLKM_BYTES, empty_b=True)


if __name__ == "__main__":
    unittest.main()
