"""Validate Android update ranges without writing the disk or its metadata."""

import argparse
import json
from pathlib import Path

from lp import (
    LP_METADATA_GEOMETRY_SIZE, LP_PARTITION_RESERVED_BYTES, LP_SECTOR_SIZE,
    LP_TARGET_TYPE_LINEAR, LpMetadataGeometry, read_at,
)

ACTIVE_PARTITIONS = {
    "system_a", "vendor_a", "product_a", "system_ext_a", "system_dlkm_a", "vendor_dlkm_a",
}


def load_allocations(path):
    allocations = json.loads(path.read_text())
    if not isinstance(allocations, dict) or allocations.keys() != ACTIVE_PARTITIONS:
        raise ValueError("Layout must specify exactly the six slot-A logical partitions")
    for name, size in allocations.items():
        if type(size) is not int or size <= 0 or size % 4096:
            raise ValueError(f"{name} allocation must be a positive, 4096-byte-aligned integer")
    return allocations


def validate_gpt_table(table):
    """Check the format and partition names reported by sfdisk."""
    if table["label"] != "gpt" or table["sectorsize"] != 512:
        raise ValueError("Expected a 512-byte-sector GPT disk")
    if table.get("unit") != "sectors":
        raise ValueError("GPT offsets must be in sectors")
    names = [entry["name"] for entry in table["partitions"]]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate GPT partition names")
    return table


def validate_super_extents(f, super_start, super_end, partitions):
    """Return safe physical ranges and the reserved prefix of a checksum-checked super partition."""
    geometry = LpMetadataGeometry.unpack(read_at(
        f, super_start + LP_PARTITION_RESERVED_BYTES, LpMetadataGeometry.size,
    ))
    metadata_max_size, metadata_slots = geometry[3:5]
    metadata_end = (super_start + LP_PARTITION_RESERVED_BYTES + 2 * LP_METADATA_GEOMETRY_SIZE
                    + 2 * metadata_max_size * metadata_slots)
    if metadata_max_size <= 0 or metadata_slots <= 0 or metadata_end >= super_end:
        raise ValueError("Invalid liblp metadata reservation")

    ranges = {}
    all_extents = []
    for partition in partitions:
        if partition.name in ranges:
            raise ValueError(f"Duplicate liblp partition: {partition.name}")
        ranges[partition.name] = []
        for extent in partition.extents:
            if extent.target_type != LP_TARGET_TYPE_LINEAR or extent.target_source != 0:
                raise ValueError(f"Unsupported liblp extent in {partition.name}")
            offset = super_start + extent.target_data * LP_SECTOR_SIZE
            length = extent.num_sectors * LP_SECTOR_SIZE
            if length <= 0 or offset < metadata_end or offset + length > super_end:
                raise ValueError(f"Extent outside super data area: {partition.name}")
            ranges[partition.name].append((offset, length))
            all_extents.append((offset, length))

    ordered = sorted(all_extents)
    if not ordered or ordered[0][0] <= super_start:
        raise ValueError("No reserved liblp metadata area")
    for (offset, length), (next_offset, _) in zip(ordered, ordered[1:]):
        if offset + length > next_offset:
            raise ValueError("Overlapping liblp extents")
    return ranges, (super_start, ordered[0][0] - super_start)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read a validated logical partition allocation")
    parser.add_argument("layout", type=Path)
    parser.add_argument("partition", choices=sorted(ACTIVE_PARTITIONS))
    args = parser.parse_args()
    try:
        print(load_allocations(args.layout)[args.partition])
    except (OSError, ValueError) as error:
        parser.exit(1, f"Android layout: {error}\n")
