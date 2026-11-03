#!/usr/bin/env python3
"""Build and verify an enlarged super image using upstream lpmake.

Never updates a disk, GPT, userdata, metadata partition or an existing output.
The CLI retains the 32 MiB experiment; fresh builds supply explicit A-only allocations.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from android_layout import ACTIVE_PARTITIONS, validate_gpt_table, validate_super_extents
from lp import (
    LP_PARTITION_RESERVED_BYTES, LP_METADATA_GEOMETRY_SIZE,
    LpMetadataGeometry, LpMetadataHeader, LpMetadataPartitionGroup,
    c_string, read_at, read_partitions,
)


VENDOR_DLKM_BYTES = 32 << 20
BLOCK_DEVICE = struct.Struct("<QIIQ36sI")


def regular_file(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular file, never a device or symlink: {path}")
    return path


def layout(f, offset, size):
    partitions = read_partitions(f, offset)
    validate_super_extents(f, offset, offset + size, partitions)
    geometry = LpMetadataGeometry.unpack(read_at(
        f, offset + LP_PARTITION_RESERVED_BYTES, LpMetadataGeometry.size))
    header_at = offset + LP_PARTITION_RESERVED_BYTES + 2 * LP_METADATA_GEOMETRY_SIZE
    header = LpMetadataHeader.unpack(read_at(f, header_at, LpMetadataHeader.size))
    if header[1:4] != (10, 2, 256):
        raise ValueError("Expected Google's liblp v10.2 header")
    flags = struct.unpack("<I", read_at(f, header_at + 128, 4))[0]
    if flags != 1:
        raise ValueError("Expected only the virtual A/B metadata flag")
    tables = read_at(f, header_at + header[3], header[5])
    descriptors = header[7:]
    group_offset, group_count, group_size = descriptors[6:9]
    if group_size != LpMetadataPartitionGroup.size:
        raise ValueError("Unexpected liblp group entry size")
    groups = []
    for index in range(group_count):
        name, group_flags, maximum = LpMetadataPartitionGroup.unpack_from(
            tables, group_offset + index * group_size)
        if group_flags:
            raise ValueError("Slot-suffixed groups are not supported by this experiment")
        groups.append((c_string(name), maximum))
    device_offset, device_count, device_size = descriptors[9:12]
    if device_count != 1 or device_size != BLOCK_DEVICE.size:
        raise ValueError("Expected a single super block device")
    _, alignment, alignment_offset, device_bytes, name, device_flags = BLOCK_DEVICE.unpack_from(
        tables, device_offset)
    if c_string(name) != "super" or device_flags or device_bytes != size:
        raise ValueError("Unexpected super block-device identity, flags or size")
    partition_offset, count, entry_size = descriptors[:3]
    if count != len(partitions) or entry_size != 52:
        raise ValueError("Unexpected partition table shape")
    for index in range(count):
        attributes = struct.unpack_from("<I", tables, partition_offset + index * entry_size + 36)[0]
        if attributes != 1:
            raise ValueError("Expected read-only logical partitions")
    return partitions, geometry, groups, alignment, alignment_offset


def image_digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def verify_payload(f, partition, path):
    """Compare every input byte and require zero-filled allocation padding."""
    with path.open("rb") as source:
        remaining = path.stat().st_size
        for extent in partition.extents:
            f.seek(extent.target_data * 512)
            extent_bytes = extent.num_sectors * 512
            while extent_bytes:
                count = min(4 << 20, extent_bytes)
                actual = f.read(count)
                payload_bytes = min(remaining, count)
                expected = source.read(payload_bytes) + bytes(count - payload_bytes)
                if len(actual) != count or actual != expected:
                    raise ValueError(f"Payload or padding differs: {partition.name}")
                remaining -= payload_bytes
                extent_bytes -= count
        if remaining:
            raise ValueError(f"Truncated payload: {partition.name}")


def build(lpmake, recovery, images, vendor_dlkm, output, allocations=None):
    regular_file(lpmake)
    regular_file(recovery)
    regular_file(vendor_dlkm)
    if images.is_symlink() or not images.is_dir():
        raise ValueError(f"Expected an image directory: {images}")
    if output.exists() or output.is_symlink():
        raise ValueError(f"Refusing to replace {output}")
    output_root = Path(__file__).resolve().parents[1] / "out"
    if not output.resolve().is_relative_to(output_root):
        raise ValueError("Disposable outputs must stay under the repository's out/")
    if output.name == "disk.img":
        raise ValueError("This experiment creates super images, never Android's disk.img")
    table = validate_gpt_table(json.loads(subprocess.check_output(
        ["sfdisk", "--json", str(recovery)], text=True))["partitiontable"])
    super_entries = [p for p in table["partitions"] if p["name"] == "super"]
    if len(super_entries) != 1:
        raise ValueError("Expected exactly one GPT super partition")
    super_entry = super_entries[0]
    size = super_entry["size"] * 512
    with recovery.open("rb") as f:
        partitions, geometry, groups, alignment, alignment_offset = layout(
            f, super_entry["start"] * 512, size)
    names = {p.name for p in partitions}
    if "vendor_dlkm_a" not in names or "system_b" not in names:
        raise ValueError("Expected the Google A/B partition layout")
    vendor_partition = next(p for p in partitions if p.name == "vendor_dlkm_a")
    if allocations is None and vendor_partition.size >= VENDOR_DLKM_BYTES:
        raise ValueError("The 32 MiB experiment must enlarge, not shrink, vendor_dlkm_a")
    if allocations is not None:
        if allocations.keys() != ACTIVE_PARTITIONS or any(
                type(value) is not int or value <= 0 or value % 4096
                for value in allocations.values()):
            raise ValueError("Expected six positive, aligned slot-A allocations")
        if sum(allocations.values()) >= size:
            raise ValueError("Logical allocations leave no room for super metadata")
        partitions = [p for p in partitions if p.name in allocations]
        if {p.name for p in partitions} != allocations.keys():
            raise ValueError("Google's source is missing an active logical partition")
        used_groups = {p.group for p in partitions} | {"default"}
        groups = [(name, maximum) for name, maximum in groups if name in used_groups]
    command = [
        str(lpmake.resolve()), "--device-size", str(size),
        "--metadata-size", str(geometry[3]), "--metadata-slots", str(geometry[4]),
        "--block-size", str(geometry[5]), "--alignment", str(alignment),
        "--alignment-offset", str(alignment_offset), "--super-name", "super",
        "--virtual-ab", "--force-full-image",
    ]
    for name, maximum in groups:
        if name != "default":
            command.extend(["--group", f"{name}:{maximum}"])
    inputs = {}
    expected_sizes = {}
    for partition in partitions:
        if partition.name.endswith("_b"):
            allocated = 0
        elif partition.name.endswith("_a") and partition.size:
            if allocations is not None:
                allocated = allocations[partition.name]
            else:
                allocated = VENDOR_DLKM_BYTES if partition.name == "vendor_dlkm_a" else partition.size
            image = vendor_dlkm if partition.name == "vendor_dlkm_a" else images / f"{partition.name}.img"
            regular_file(image)
            if image.stat().st_size > allocated:
                raise ValueError(f"{partition.name} does not fit its allocation")
            inputs[partition.name] = image
            command.extend(["--image", f"{partition.name}={image.resolve()}"])
        else:
            raise ValueError(f"Unexpected logical partition: {partition.name}")
        expected_sizes[partition.name] = allocated
        command.extend(["--partition", f"{partition.name}:readonly:{allocated}:{partition.group}"])
    before = {name: image_digest(path) for name, path in inputs.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=output.name + ".partial.", dir=output.parent) as temporary:
        candidate = Path(temporary) / "super.img"
        subprocess.run([*command, "--output", str(candidate)], check=True)
        if candidate.stat().st_size != size:
            raise ValueError("Generated super size differs from the outer GPT allocation")
        with candidate.open("rb") as f:
            generated, new_geometry, new_groups, new_alignment, new_offset = layout(f, 0, size)
            if (new_geometry, new_groups, new_alignment, new_offset) != (
                    geometry, groups, alignment, alignment_offset):
                raise ValueError("Generated geometry or group limits differ")
            if {p.name: p.size for p in generated} != expected_sizes:
                raise ValueError("Generated partition sizes differ from the requested layout")
            if {p.name: p.group for p in generated} != {p.name: p.group for p in partitions}:
                raise ValueError("Generated partition groups differ")
            metadata_start = LP_PARTITION_RESERVED_BYTES + 2 * LP_METADATA_GEOMETRY_SIZE
            primary = read_at(f, metadata_start, geometry[3])
            for slot in range(geometry[4] * 2):
                if read_at(f, metadata_start + slot * geometry[3], geometry[3]) != primary:
                    raise ValueError("Primary/backup metadata slots differ")
            for partition in generated:
                if partition.name in inputs:
                    verify_payload(f, partition, inputs[partition.name])
        if before != {name: image_digest(path) for name, path in inputs.items()}:
            raise ValueError("An input changed during image creation")
        # Hard-link publication fails atomically if another writer creates the destination.
        output.hardlink_to(candidate)
    vendor_bytes = expected_sizes["vendor_dlkm_a"]
    b_state = "logical B partitions removed" if allocations is not None else "all B allocations empty"
    print(f"Verified {output}: vendor_dlkm_a={vendor_bytes} bytes; "
          f"{b_state}, all A payloads verified, GPT untouched")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("lpmake", "recovery", "images", "vendor_dlkm", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        build(args.lpmake, args.recovery, args.images, args.vendor_dlkm, args.output)
    except (OSError, ValueError, KeyError, struct.error, subprocess.CalledProcessError) as error:
        parser.exit(1, f"super candidate: {error}\n")


if __name__ == "__main__":
    main()
