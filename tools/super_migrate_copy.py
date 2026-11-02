#!/usr/bin/env python3
"""Migrate Google's slot-A super layout on a new disposable regular-file copy only.

Keep all active payloads and every byte outside super; never modify the source,
physical devices, an existing destination or the working Android disk.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from android_layout import validate_gpt_table, validate_super_extents
from android_sync import copy_component, disk_hash
from lp import (
    LP_METADATA_GEOMETRY_SIZE, LP_PARTITION_RESERVED_BYTES,
    extract, read_at, read_partitions,
)
from super_candidate import VENDOR_DLKM_BYTES, build, image_digest, layout, regular_file


OUT = Path(__file__).resolve().parents[1] / "out"
ACTIVE_NAMES = {
    "system_a", "vendor_a", "product_a", "system_ext_a", "system_dlkm_a", "vendor_dlkm_a",
}


def output_path(path):
    if path.exists() or path.is_symlink():
        raise ValueError(f"Refusing to replace {path}")
    if not path.resolve().is_relative_to(OUT) or path.name == "disk.img":
        raise ValueError("Migration outputs must be disposable files under out/, never disk.img")


def check_slot_a(physical):
    if not {"super", "vbmeta_a", "vbmeta_b", "userdata", "metadata", "EFI-SYSTEM"} <= physical.keys():
        raise ValueError("Expected the Android USB partition layout")
    if physical["vbmeta_a"].get("attrs") != "GUID:48,49,50,51,56" or physical["vbmeta_b"].get("attrs"):
        raise ValueError("Migration requires successful slot A and inactive slot B")


def compare_outside_super(source, candidate, start, end):
    size = source.stat().st_size
    if candidate.stat().st_size != size:
        raise ValueError("Candidate disk size differs from the source")
    with source.open("rb") as before, candidate.open("rb") as after:
        for first, last in ((0, start), (end, size)):
            before.seek(first)
            after.seek(first)
            remaining = last - first
            while remaining:
                count = min(8 << 20, remaining)
                original = before.read(count)
                if len(original) != count or original != after.read(count):
                    raise ValueError("Bytes outside super differ (GPT/userdata/metadata/boot)")
                remaining -= count


def migrate(lpmake, source, destination):
    regular_file(source)
    regular_file(lpmake)
    output_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(str(source) + ".lock")
    if lock_path.is_symlink():
        raise ValueError("Refusing a symlinked source lock")
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Stop the VM before preparing a migration copy") from error
        table = validate_gpt_table(json.loads(subprocess.check_output(
            ["sfdisk", "--json", str(source)], text=True))["partitiontable"])
        subprocess.run(["sfdisk", "--verify", str(source)], check=True)
        physical = {p["name"]: p for p in table["partitions"]}
        check_slot_a(physical)
        start = physical["super"]["start"] * 512
        size = physical["super"]["size"] * 512
        if start <= 0 or start + size > source.stat().st_size:
            raise ValueError("Super partition lies outside the source disk")
        with source.open("rb") as disk:
            partitions, geometry, *_ = layout(disk, start, size)
            if {p.name for p in partitions} != ACTIVE_NAMES | {
                    name[:-1] + "b" for name in ACTIVE_NAMES}:
                raise ValueError("Unexpected logical partition set")
            primary_at = start + LP_PARTITION_RESERVED_BYTES + 2 * LP_METADATA_GEOMETRY_SIZE
            primary = read_at(disk, primary_at, geometry[3])
            for index in range(geometry[4] * 2):
                if read_at(disk, primary_at + index * geometry[3], geometry[3]) != primary:
                    raise ValueError("Source primary/backup metadata copies disagree")
            vendor = next(p for p in partitions if p.name == "vendor_dlkm_a")
            if vendor.size == VENDOR_DLKM_BYTES and all(
                    not p.size for p in partitions if p.name.endswith("_b")):
                print("Source already has the 32 MiB layout; no copy or partitions written.")
                return
            if vendor.size != 18096128:
                raise ValueError("Expected Google's original 18,096,128-byte vendor_dlkm_a")
            if any(not p.size for p in partitions if p.name in ACTIVE_NAMES):
                raise ValueError("An active logical partition is empty")
            with tempfile.TemporaryDirectory(
                    prefix=destination.name + ".partial.", dir=destination.parent) as temporary:
                work = Path(temporary)
                images = work / "images"
                images.mkdir()
                for partition in partitions:
                    if partition.name in ACTIVE_NAMES:
                        extract(disk, start, partition, images / f"{partition.name}.img")
                super_image = work / "super.img"
                build(lpmake, source, images, images / "vendor_dlkm_a.img", super_image)
                candidate = work / "migrated.img"
                subprocess.run(["cp", "--reflink=auto", "--sparse=always",
                                str(source), str(candidate)], check=True)
                with candidate.open("r+b") as output:
                    copy_component(output, super_image, [(start, size)])
                    if disk_hash(output, [(start, size)], size) != image_digest(super_image):
                        raise ValueError("Migrated super differs from the verified generated image")
                    validate_super_extents(output, start, start + size,
                                           read_partitions(output, start))
                compare_outside_super(source, candidate, start, start + size)
                candidate.chmod(0o600)
                with candidate.open("rb") as output:
                    os.fsync(output.fileno())
                destination.hardlink_to(candidate)
                directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        print(f"Verified migration copy: {destination}; all A payloads, GPT, userdata, "
              "metadata and boot files preserved. Source untouched.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("lpmake", "source", "destination"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        migrate(args.lpmake, args.source, args.destination)
    except (OSError, ValueError, KeyError, struct.error, subprocess.CalledProcessError) as error:
        parser.exit(1, f"super migration copy: {error}\n")


if __name__ == "__main__":
    main()
