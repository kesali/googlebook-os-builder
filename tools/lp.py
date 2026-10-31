#!/usr/bin/env python3
"""Read the logical partitions inside an Android "super" partition.

    lp.py list    <image> [--offset BYTES]
    lp.py extract <image> <out-dir> [--offset BYTES] [NAME ...]

<image> is a file holding a super partition that starts --offset bytes into
it (for example a whole-disk recovery image). `list` prints one line per
logical partition. `extract` writes <out-dir>/<name>.img for each NAME, or
for every non-empty partition when no NAME is given.

The on-disk format is defined in AOSP
system/core/fs_mgr/liblp/include/liblp/metadata_format.h; the constant and
struct names below match the ones there.
"""

import argparse
import hashlib
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

LP_SECTOR_SIZE = 512
LP_PARTITION_RESERVED_BYTES = 4096
LP_METADATA_GEOMETRY_SIZE = 4096
LP_METADATA_GEOMETRY_MAGIC = 0x616C4467
LP_METADATA_HEADER_MAGIC = 0x414C5030
LP_TARGET_TYPE_LINEAR = 0
LP_TARGET_TYPE_ZERO = 1

# struct LpMetadataGeometry:
#   magic, struct_size, checksum, metadata_max_size, metadata_slot_count, logical_block_size
LpMetadataGeometry = struct.Struct("<I I 32s I I I")
GEOMETRY_CHECKSUM_OFFSET = 8

# struct LpMetadataHeader, up to its four table descriptors (offset, num_entries, entry_size):
#   magic, major_version, minor_version, header_size, header_checksum,
#   tables_size, tables_checksum, partitions[3], extents[3], groups[3], block_devices[3]
LpMetadataHeader = struct.Struct("<I H H I 32s I 32s 3I 3I 3I 3I")
HEADER_CHECKSUM_OFFSET = 12

# Table entries.
LpMetadataPartition = struct.Struct("<36s I I I I")  # name, attributes, first_extent_index, num_extents, group_index
LpMetadataExtent = struct.Struct("<Q I Q I")  # num_sectors, target_type, target_data, target_source
LpMetadataPartitionGroup = struct.Struct("<36s I Q")  # name, flags, maximum_size


@dataclass
class Extent:
    num_sectors: int
    target_type: int  # LP_TARGET_TYPE_LINEAR or LP_TARGET_TYPE_ZERO
    target_data: int  # LINEAR: first sector of this extent inside super
    target_source: int  # LINEAR: block device index; 0 is super itself


@dataclass
class Partition:
    name: str
    group: str
    extents: list

    @property
    def size(self):
        return sum(e.num_sectors for e in self.extents) * LP_SECTOR_SIZE


def read_at(f, offset, size):
    f.seek(offset)
    data = f.read(size)
    if len(data) != size:
        sys.exit(f"lp.py: file ends before byte {offset + size}")
    return data


def check_sha256(what, blob, checksum_offset, expected):
    """liblp checksums are SHA-256 of the struct with its checksum field zeroed."""
    zeroed = blob[:checksum_offset] + bytes(32) + blob[checksum_offset + 32 :]
    if hashlib.sha256(zeroed).digest() != expected:
        sys.exit(f"lp.py: {what} checksum mismatch")


def c_string(raw):
    return raw.split(b"\0", 1)[0].decode()


def read_partitions(f, super_offset):
    """Return the logical partitions described by metadata slot 0."""
    geometry_at = super_offset + LP_PARTITION_RESERVED_BYTES
    magic, struct_size, checksum, *_ = LpMetadataGeometry.unpack(
        read_at(f, geometry_at, LpMetadataGeometry.size)
    )
    if magic != LP_METADATA_GEOMETRY_MAGIC:
        sys.exit("lp.py: no super partition metadata found (wrong --offset?)")
    check_sha256("geometry", read_at(f, geometry_at, struct_size), GEOMETRY_CHECKSUM_OFFSET, checksum)

    # Layout: reserved bytes, primary geometry, backup geometry, metadata slot 0, ...
    header_at = geometry_at + 2 * LP_METADATA_GEOMETRY_SIZE
    magic, _major, _minor, header_size, header_checksum, tables_size, tables_checksum, *descriptors = (
        LpMetadataHeader.unpack(read_at(f, header_at, LpMetadataHeader.size))
    )
    if magic != LP_METADATA_HEADER_MAGIC:
        sys.exit("lp.py: bad metadata header magic")
    check_sha256("header", read_at(f, header_at, header_size), HEADER_CHECKSUM_OFFSET, header_checksum)
    tables = read_at(f, header_at + header_size, tables_size)
    if hashlib.sha256(tables).digest() != tables_checksum:
        sys.exit("lp.py: tables checksum mismatch")

    def table(index, entry):
        """Entries of table `index` (0 partitions, 1 extents, 2 groups, 3 block devices)."""
        offset, count, entry_size = descriptors[3 * index : 3 * index + 3]
        return [entry.unpack_from(tables, offset + i * entry_size) for i in range(count)]

    extents = [Extent(*e) for e in table(1, LpMetadataExtent)]
    groups = [c_string(name) for name, _flags, _maximum_size in table(2, LpMetadataPartitionGroup)]
    return [
        Partition(c_string(name), groups[group], extents[first : first + count])
        for name, _attributes, first, count, group in table(0, LpMetadataPartition)
    ]


def copy_bytes(src, offset, length, dst, chunk=4 << 20):
    src.seek(offset)
    while length:
        data = src.read(min(chunk, length))
        if not data:
            sys.exit("lp.py: file ends inside a partition")
        dst.write(data)
        length -= len(data)


def extract(f, super_offset, partition, path):
    with open(path, "wb") as out:
        for e in partition.extents:
            length = e.num_sectors * LP_SECTOR_SIZE
            if e.target_type == LP_TARGET_TYPE_ZERO:
                out.seek(length, 1)  # leave a hole; it reads back as zeros
            elif e.target_type == LP_TARGET_TYPE_LINEAR and e.target_source == 0:
                copy_bytes(f, super_offset + e.target_data * LP_SECTOR_SIZE, length, out)
            else:
                sys.exit(f"lp.py: {partition.name}: extent type {e.target_type} on device {e.target_source} unsupported")
        out.truncate()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["list", "extract"])
    parser.add_argument("image")
    parser.add_argument("out_dir", nargs="?", help="extract: where to write <name>.img")
    parser.add_argument("names", nargs="*", help="extract: partitions to write (default: all non-empty)")
    parser.add_argument("--offset", type=int, default=0, help="byte offset of super inside <image>")
    args = parser.parse_args()

    with open(args.image, "rb") as f:
        partitions = read_partitions(f, args.offset)

        if args.command == "list":
            print(f"{'name':<16} {'bytes':>12}  group")
            for p in partitions:
                print(f"{p.name:<16} {p.size:>12}  {p.group}")
            return

        if not args.out_dir:
            parser.error("extract needs <out-dir>")
        by_name = {p.name: p for p in partitions}
        unknown = [n for n in args.names if n not in by_name]
        if unknown:
            sys.exit(f"lp.py: no such partition: {', '.join(unknown)}")
        wanted = [by_name[n] for n in args.names] or [p for p in partitions if p.size > 0]
        Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        for p in wanted:
            print(f"   {p.name} ({p.size // (1 << 20)} MiB)")
            extract(f, args.offset, p, Path(args.out_dir) / f"{p.name}.img")


if __name__ == "__main__":
    main()
