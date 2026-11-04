"""Test fresh-image publication, layout choices and refusal without physical disks."""

from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from android_fresh import check_output, create
from android_layout import ACTIVE_PARTITIONS, load_allocations
from lp import Extent, Partition
from super_candidate import build

REPO = Path(__file__).resolve().parents[1]


class FreshImageTests(unittest.TestCase):
    def test_declared_allocations_match_approved_sizes(self):
        self.assertEqual(load_allocations(REPO / "android/super-layout.json"), {
            "system_a": 2 << 30, "vendor_a": 1 << 30, "product_a": 3 << 30,
            "system_ext_a": 1 << 30, "system_dlkm_a": 64 << 20,
            "vendor_dlkm_a": 64 << 20,
        })

    def test_layout_rejects_missing_extra_and_invalid_sizes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "layout.json"
            good = {name: 4096 for name in ACTIVE_PARTITIONS}
            cases = [[], {}, {**good, "system_b": 4096}]
            for bad in (True, "4096", 0, -4096, 4097, 4096.0):
                cases.append({**good, "vendor_dlkm_a": bad})
            for value in cases:
                with self.subTest(value=value):
                    path.write_text(json.dumps(value))
                    with self.assertRaises(ValueError):
                        load_allocations(path)

    def test_output_refuses_existing_symlink_outside_out_and_old_disk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = root / "android/disk.img"
            existing = root / "existing"
            existing.write_bytes(b"keep")
            link = root / "link"
            link.symlink_to(root / "missing")
            with patch("android_fresh.OUT", root):
                for path in (existing, link, root.parent / "outside.img", old):
                    with self.subTest(path=path), self.assertRaises(ValueError):
                        check_output(path)
            self.assertEqual(existing.read_bytes(), b"keep")

    def exercise_creation(self, root, fail_boot=False, corrupt_write=False):
        recovery = root / "recovery"
        recovery.write_bytes(b"recovery")
        google = root / "google"
        (google / "super").mkdir(parents=True)
        artifacts = root / "artifacts"
        artifacts.mkdir()
        allocations = {name: 4096 for name in ACTIVE_PARTITIONS}
        layout_path = root / "layout.json"
        layout_path.write_text(json.dumps(allocations))
        for name in allocations:
            directory = google / "super" if name in ("product_a", "system_dlkm_a") else artifacts
            (directory / f"{name}.img").write_bytes(name.encode())
        destination = root / "expanded/disk.img"
        super_bytes = b"S" * 1024

        def generate(lpmake, source, images, vendor, output, requested):
            self.assertEqual(requested, allocations)
            self.assertEqual({p.stem for p in images.iterdir()}, ACTIVE_PARTITIONS)
            output.write_bytes(super_bytes)

        def run(args, **kwargs):
            if args[0] == "cp":
                shutil.copyfile(args[-2], args[-1])
            elif args[1] == "scripts/android-disk.sh":
                Path(args[-1]).write_bytes(b"P" * 512 + bytes(1024) + b"U" * 512)
            elif args[1:2] == ["scripts/android-boot.sh"] and fail_boot:
                raise subprocess.CalledProcessError(1, args)

        table = {"label": "gpt", "sectorsize": 512, "unit": "sectors",
                 "partitions": [{"name": "super", "start": 1, "size": 2}]}
        with ExitStack() as patches:
            patches.enter_context(patch("android_fresh.OUT", root))
            patches.enter_context(patch("android_fresh.build", side_effect=generate))
            patches.enter_context(patch("android_fresh.subprocess.run", side_effect=run))
            patches.enter_context(patch("android_fresh.subprocess.check_output",
                                        return_value=json.dumps({"partitiontable": table})))
            updater = patches.enter_context(patch("android_fresh.sync"))
            if corrupt_write:
                patches.enter_context(patch("android_fresh.copy_component"))
            if fail_boot or corrupt_write:
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    create(recovery, recovery, google, artifacts, layout_path, 1, destination)
                self.assertFalse(destination.exists())
            else:
                create(recovery, recovery, google, artifacts, layout_path, 1, destination)
                self.assertEqual(destination.read_bytes(), b"P" * 512 + super_bytes + b"U" * 512)
                self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
                updater.assert_called_once()
                with self.assertRaisesRegex(ValueError, "Refusing to replace"):
                    create(recovery, recovery, google, artifacts, layout_path, 1, destination)
        self.assertEqual(recovery.read_bytes(), b"recovery")
        self.assertFalse(list(destination.parent.glob("fresh.partial.*")))

    def test_verified_copy_is_published_privately_and_never_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.exercise_creation(Path(temporary))

    def test_boot_install_failure_leaves_no_published_disk(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.exercise_creation(Path(temporary), fail_boot=True)

    def test_super_readback_failure_leaves_no_published_disk(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.exercise_creation(Path(temporary), corrupt_write=True)

    def test_super_command_removes_b_partitions_and_group(self):
        with tempfile.TemporaryDirectory(dir=REPO / "out") as temporary:
            root = Path(temporary)
            source = root / "recovery"
            source.write_bytes(b"source")
            allocations = {name: 4096 for name in ACTIVE_PARTITIONS}
            for name in allocations:
                (root / f"{name}.img").write_bytes(b"payload")
            originals = []
            for index, name in enumerate(sorted(allocations)):
                originals.append(Partition(name, "group_a", [Extent(8, 0, 64 + index * 8, 0)]))
                originals.append(Partition(name[:-1] + "b", "group_b", []))
            generated = [p for p in originals if p.name in allocations]
            groups = [("default", 0), ("group_a", 1 << 20), ("group_b", 1 << 20)]
            geometry = (0, 0, 0, 64, 3, 4096)
            table = {"label": "gpt", "sectorsize": 512, "unit": "sectors",
                     "partitions": [{"name": "super", "start": 1, "size": 2048}]}
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                with Path(command[-1]).open("wb") as output:
                    output.truncate(1 << 20)

            with patch("super_candidate.subprocess.check_output",
                       return_value=json.dumps({"partitiontable": table})), \
                    patch("super_candidate.layout", side_effect=[
                        (originals, geometry, groups, 4096, 0),
                        (generated, geometry, groups[:2], 4096, 0)]), \
                    patch("super_candidate.subprocess.run", side_effect=run), \
                    patch("super_candidate.verify_payload") as verify:
                output = root / "super.img"
                build(source, source, root, root / "vendor_dlkm_a.img", output, allocations)
                self.assertTrue(output.is_file())
                self.assertEqual(verify.call_count, 6)
            command = calls[0]
            entries = [command[index + 1] for index, word in enumerate(command) if word == "--partition"]
            self.assertEqual({entry.split(":")[0] for entry in entries}, ACTIVE_PARTITIONS)
            self.assertTrue(all(":readonly:4096:group_a" in entry for entry in entries))
            self.assertNotIn("group_b:1048576", command)

    def test_make_routes_build_vm_and_updater_to_new_disk(self):
        makefile = (REPO / "Makefile").read_text()
        self.assertIn("ANDROID_DISK := $(OUT)/gbos-builder/disk.img", makefile)
        self.assertIn('--layout "$(ANDROID_LAYOUT)"', makefile)
        self.assertNotIn('"$(ANDROID)/disk.img"', makefile)
        smoke = (REPO / "tools/android_smoke.py").read_text()
        self.assertIn('disk = Path(sys.argv[4])', smoke.split("def main():")[1])
        self.assertIn('out / "gbos-builder/disk.img"', smoke.split("def main():")[1])
        self.assertNotIn("sys.argv", smoke.split("def verify(")[1].split("def main():")[0])
        uefi = (REPO / "tools/android_uefi_test.py").read_text().split("def main():")[1]
        self.assertIn('args.out / "gbos-builder/disk.img"', uefi)


if __name__ == "__main__":
    unittest.main()
