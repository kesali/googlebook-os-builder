"""Check private Android image updates using temporary regular-file fixtures."""

import copy
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import struct
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from android_sync import copy_component, disk_hash, sync
from android_smoke import check_scanout
from lp import (
    GEOMETRY_CHECKSUM_OFFSET, HEADER_CHECKSUM_OFFSET, LP_METADATA_GEOMETRY_MAGIC,
    LP_METADATA_GEOMETRY_SIZE, LP_METADATA_HEADER_MAGIC, LP_PARTITION_RESERVED_BYTES,
    LP_TARGET_TYPE_LINEAR, Extent, LpMetadataExtent, LpMetadataGeometry, LpMetadataHeader,
    LpMetadataPartition, LpMetadataPartitionGroup, Partition,
)


def write_super_metadata(image, super_start, partitions, metadata_max_size=1024,
                         corrupt_tables=False):
    partition_table = bytearray()
    extent_table = bytearray()
    for partition in partitions:
        first = len(extent_table) // LpMetadataExtent.size
        count = len(partition.extents)
        partition_table.extend(LpMetadataPartition.pack(
            partition.name.encode(), 0, first, count, 0,
        ))
        for extent in partition.extents:
            extent_table.extend(LpMetadataExtent.pack(
                extent.num_sectors, extent.target_type, extent.target_data, extent.target_source,
            ))
    group_table = LpMetadataPartitionGroup.pack(b"group", 0, 0)
    tables = bytes(partition_table + extent_table + group_table)
    descriptors = (
        0, len(partitions), LpMetadataPartition.size,
        len(partition_table), len(extent_table) // LpMetadataExtent.size, LpMetadataExtent.size,
        len(partition_table) + len(extent_table), 1, LpMetadataPartitionGroup.size,
        len(tables), 0, 0,
    )
    geometry = LpMetadataGeometry.pack(
        LP_METADATA_GEOMETRY_MAGIC, LpMetadataGeometry.size, bytes(32),
        metadata_max_size, 1, 4096,
    )
    geometry = (geometry[:GEOMETRY_CHECKSUM_OFFSET] + hashlib.sha256(geometry).digest()
                + geometry[GEOMETRY_CHECKSUM_OFFSET + 32:])
    header = LpMetadataHeader.pack(
        LP_METADATA_HEADER_MAGIC, 10, 0, LpMetadataHeader.size, bytes(32),
        len(tables), hashlib.sha256(tables).digest(), *descriptors,
    )
    header = (header[:HEADER_CHECKSUM_OFFSET] + hashlib.sha256(header).digest()
              + header[HEADER_CHECKSUM_OFFSET + 32:])
    if corrupt_tables:
        tables = bytes([tables[0] ^ 1]) + tables[1:]
    with image.open("r+b") as disk:
        disk.seek(super_start + LP_PARTITION_RESERVED_BYTES)
        disk.write(geometry)
        disk.seek(super_start + LP_PARTITION_RESERVED_BYTES + 2 * LP_METADATA_GEOMETRY_SIZE)
        disk.write(header + tables)


def make_sync_fixture(root, real_gpt=False):
    image = root / "disk.img"
    if real_gpt:
        with image.open("wb") as disk:
            disk.truncate(8 * 1024 * 1024)
        subprocess.run(
            ["sfdisk", "--quiet", "--no-reread", str(image)],
            input='label: gpt\nunit: sectors\n\n'
                  'start=2048, size=256, type=L, name="super"\n'
                  'start=4096, size=1, type=L, name="vbmeta_a"\n',
            text=True, check=True, capture_output=True,
        )
        table = json.loads(subprocess.check_output(["sfdisk", "--json", str(image)]))["partitiontable"]
    else:
        image.write_bytes(b"D" * (96 * 512))
        table = {"label": "gpt", "sectorsize": 512, "unit": "sectors", "partitions": [
            {"name": "super", "start": 2, "size": 70},
            {"name": "vbmeta_a", "start": 80, "size": 1},
        ]}
    logical = [
        Partition("system_a", "group", [Extent(1, LP_TARGET_TYPE_LINEAR, 28, 0)]),
        Partition("vendor_a", "group", [
            Extent(1, LP_TARGET_TYPE_LINEAR, 32, 0),
            Extent(1, LP_TARGET_TYPE_LINEAR, 36, 0),
        ]),
        Partition("system_ext_a", "group", [Extent(1, LP_TARGET_TYPE_LINEAR, 40, 0)]),
        Partition("vendor_dlkm_a", "group", [Extent(1, LP_TARGET_TYPE_LINEAR, 44, 0)]),
    ]
    physical = {part["name"]: part for part in table["partitions"]}
    write_super_metadata(image, physical["super"]["start"] * 512, logical)
    for partition in logical:
        data = b"V" * 600 if partition.name == "vendor_a" else partition.name.encode()
        (root / f"{partition.name}.img").write_bytes(data)
    (root / "vbmeta_a.img").write_bytes(b"vbmeta_a")
    return image, table, logical


def expected_update(before, root, table, logical):
    expected = bytearray(before)
    physical = {part["name"]: part for part in table["partitions"]}
    super_start = physical["super"]["start"] * 512
    for partition in logical:
        source = (root / f"{partition.name}.img").read_bytes()
        position = 0
        for extent in partition.extents:
            offset = super_start + extent.target_data * 512
            length = extent.num_sectors * 512
            expected[offset:offset + length] = source[position:position + length].ljust(length, b"\0")
            position += length
    vbmeta = physical["vbmeta_a"]
    offset, length = vbmeta["start"] * 512, vbmeta["size"] * 512
    expected[offset:offset + length] = (root / "vbmeta_a.img").read_bytes().ljust(length, b"\0")
    return bytes(expected)


class AndroidTests(unittest.TestCase):
    def test_declared_layout_mismatch_rejects_all_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, table, partitions = make_sync_fixture(root, real_gpt=True)
            before = image.read_bytes()
            timestamp = image.stat().st_mtime_ns
            sizes = {p.name: p.size for p in partitions}
            for changed in ({**sizes, "vendor_dlkm_a": 4096},
                            {**sizes, "system_b": 0}):
                with self.subTest(changed=changed), \
                        self.assertRaisesRegex(ValueError, "Disk layout differs"):
                    sync(image, root, changed)
                self.assertEqual(image.read_bytes(), before)
                self.assertEqual(image.stat().st_mtime_ns, timestamp)
            sync(image, root, sizes)
            self.assertEqual(image.read_bytes(), expected_update(before, root, table, partitions))

    def test_vendor_dlkm_update_preserves_other_bytes_and_is_a_noop_when_equal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, table, logical = make_sync_fixture(root)
            before = image.read_bytes()
            with patch("android_sync.subprocess.check_output",
                       return_value=json.dumps({"partitiontable": table}).encode()), \
                    patch("android_sync.subprocess.run") as verify:
                sync(image, root)
                verify.assert_called_once_with(["sfdisk", "--verify", str(image)], check=True)
                data = image.read_bytes()
                self.assertEqual(data, expected_update(before, root, table, logical))
                first_vendor = (2 + 32) * 512
                second_vendor = (2 + 36) * 512
                self.assertEqual(data[first_vendor:first_vendor + 512], b"V" * 512)
                self.assertEqual(data[second_vendor:second_vendor + 88], b"V" * 88)
                timestamp = image.stat().st_mtime_ns
                sync(image, root)
                self.assertEqual(image.stat().st_mtime_ns, timestamp)
                self.assertEqual(image.read_bytes(), data)
                (root / "system_a.img").write_bytes(b"would otherwise be updated")
                (root / "vendor_dlkm_a.img").write_bytes(b"oversized" * 100)
                with self.assertRaisesRegex(ValueError, "does not fit vendor_dlkm_a"):
                    sync(image, root)
                self.assertEqual(image.stat().st_mtime_ns, timestamp)
                self.assertEqual(image.read_bytes(), data)

    def test_sync_accepts_a_verified_gpt_on_a_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, table, logical = make_sync_fixture(root, real_gpt=True)
            before = image.read_bytes()
            sync(image, root)
            data = image.read_bytes()
            self.assertEqual(data, expected_update(before, root, table, logical))
            timestamp = image.stat().st_mtime_ns
            sync(image, root)
            self.assertEqual(image.stat().st_mtime_ns, timestamp)
            self.assertEqual(image.read_bytes(), data)

    def test_invalid_extents_refuse_all_writes_even_in_a_later_partition(self):
        cases = (
            ("metadata", Extent(1, 0, 27, 0), "outside super data area"),
            ("overlap", Extent(1, 0, 28, 0), "Overlapping liblp extents"),
            ("zero length", Extent(0, 0, 44, 0), "outside super data area"),
            ("outside super", Extent(100, 0, 44, 0), "outside super data area"),
            ("unsupported type", Extent(1, 1, 44, 0), "Unsupported liblp extent"),
            ("unsupported source", Extent(1, 0, 44, 1), "Unsupported liblp extent"),
        )
        for name, extent, error in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                image, table, logical = make_sync_fixture(root)
                logical[-1].extents = [extent]
                write_super_metadata(image, 2 * 512, logical)
                before, timestamp = image.read_bytes(), image.stat().st_mtime_ns
                with patch("android_sync.subprocess.check_output",
                           return_value=json.dumps({"partitiontable": table}).encode()), \
                        patch("android_sync.subprocess.run"), \
                        patch("android_sync.copy_component") as write_component:
                    with self.assertRaisesRegex(ValueError, error):
                        sync(image, root)
                    write_component.assert_not_called()
                self.assertEqual(image.read_bytes(), before)
                self.assertEqual(image.stat().st_mtime_ns, timestamp)

    def test_unupdated_and_duplicate_logical_partitions_cannot_hide_conflicts(self):
        cases = (
            (Partition("product_a", "group", [Extent(1, 0, 28, 0)]),
             "Overlapping liblp extents"),
            (Partition("system_a", "group", [Extent(1, 0, 52, 0)]),
             "Duplicate liblp partition"),
        )
        for extra, error in cases:
            with self.subTest(partition=extra.name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                image, table, logical = make_sync_fixture(root)
                logical.append(extra)
                write_super_metadata(image, 2 * 512, logical)
                before, timestamp = image.read_bytes(), image.stat().st_mtime_ns
                with patch("android_sync.subprocess.check_output",
                           return_value=json.dumps({"partitiontable": table}).encode()), \
                        patch("android_sync.subprocess.run"), \
                        patch("android_sync.copy_component") as write_component:
                    with self.assertRaisesRegex(ValueError, error):
                        sync(image, root)
                    write_component.assert_not_called()
                self.assertEqual(image.read_bytes(), before)
                self.assertEqual(image.stat().st_mtime_ns, timestamp)

    def test_invalid_liblp_metadata_refuses_without_writing(self):
        cases = (
            ({"metadata_max_size": 0}, ValueError, "Invalid liblp metadata reservation"),
            ({"corrupt_tables": True}, SystemExit, "tables checksum mismatch"),
        )
        for options, exception, error in cases:
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                image, table, logical = make_sync_fixture(root)
                write_super_metadata(image, 2 * 512, logical, **options)
                before, timestamp = image.read_bytes(), image.stat().st_mtime_ns
                with patch("android_sync.subprocess.check_output",
                           return_value=json.dumps({"partitiontable": table}).encode()), \
                        patch("android_sync.subprocess.run"), \
                        patch("android_sync.copy_component") as write_component:
                    with self.assertRaisesRegex(exception, error):
                        sync(image, root)
                    write_component.assert_not_called()
                self.assertEqual(image.read_bytes(), before)
                self.assertEqual(image.stat().st_mtime_ns, timestamp)

    def test_invalid_gpt_is_rejected_before_reading_logical_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, table, _ = make_sync_fixture(root)
            before, timestamp = image.read_bytes(), image.stat().st_mtime_ns
            failure = subprocess.CalledProcessError(1, ["sfdisk", "--verify", str(image)])
            with patch("android_sync.subprocess.check_output",
                       return_value=json.dumps({"partitiontable": table}).encode()), \
                    patch("android_sync.subprocess.run", side_effect=failure) as verify, \
                    patch("android_sync.read_partitions") as read_logical:
                with self.assertRaises(subprocess.CalledProcessError):
                    sync(image, root)
                verify.assert_called_once_with(["sfdisk", "--verify", str(image)], check=True)
                read_logical.assert_not_called()
            self.assertEqual(image.read_bytes(), before)
            self.assertEqual(image.stat().st_mtime_ns, timestamp)

    def test_non_sector_and_duplicate_gpt_partitions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, table, _ = make_sync_fixture(root)
            cases = []
            non_sector = copy.deepcopy(table)
            non_sector["unit"] = "bytes"
            cases.append((non_sector, "GPT offsets must be in sectors"))
            duplicate = copy.deepcopy(table)
            duplicate["partitions"].append(copy.deepcopy(duplicate["partitions"][0]))
            cases.append((duplicate, "Duplicate GPT partition names"))
            before, timestamp = image.read_bytes(), image.stat().st_mtime_ns
            for invalid, error in cases:
                with self.subTest(error=error), patch(
                    "android_sync.subprocess.check_output",
                    return_value=json.dumps({"partitiontable": invalid}).encode(),
                ), patch("android_sync.subprocess.run") as verify:
                    with self.assertRaisesRegex(ValueError, error):
                        sync(image, root)
                    verify.assert_not_called()
                self.assertEqual(image.read_bytes(), before)
                self.assertEqual(image.stat().st_mtime_ns, timestamp)

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
