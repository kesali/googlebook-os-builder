#!/usr/bin/env python3
"""Update only rebuilt OS partitions in the private QEMU disk, never Android's data.

This copies whole filesystem/AVB images into their named partitions; it never
patches executable bytes or edits liblp metadata. An interrupted update is repaired
by rerunning it. The same lock is held by the QEMU runner.
"""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

from lp import LP_TARGET_TYPE_LINEAR, read_partitions

CHUNK = 4 << 20


def copy_component(disk, source, extents):
    remaining = source.stat().st_size
    with source.open("rb") as stream:
        for offset, length in extents:
            disk.seek(offset)
            while length:
                count = min(length, CHUNK)
                data = stream.read(min(count, remaining))
                remaining -= len(data)
                disk.write(data + bytes(count - len(data)))
                length -= count
    disk.flush()
    os.fsync(disk.fileno())


def disk_hash(disk, extents, size):
    result = hashlib.sha256()
    for offset, length in extents:
        disk.seek(offset)
        remaining = min(length, size)
        size -= remaining
        while remaining:
            data = disk.read(min(CHUNK, remaining))
            if not data:
                raise ValueError("Disk ends inside an OS partition")
            result.update(data)
            remaining -= len(data)
    if size:
        raise ValueError("Component exceeds its partition")
    return result.hexdigest()


def sync(image, artifacts):
    if image.is_symlink() or not stat.S_ISREG(image.stat().st_mode):
        raise ValueError("Android updates accept only a regular disk image, never a device/symlink")
    with Path(str(image) + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Stop QEMU before updating its disk") from error
        table = json.loads(subprocess.check_output(["sfdisk", "--json", str(image)]))["partitiontable"]
        if table["label"] != "gpt" or table["sectorsize"] != 512:
            raise ValueError("Expected a 512-byte-sector GPT Android disk")
        physical = {p["name"]: p for p in table["partitions"]}
        super_start = physical["super"]["start"] * 512
        super_end = super_start + physical["super"]["size"] * 512
        with image.open("r+b") as disk:
            logical = {p.name: p for p in read_partitions(disk, super_start)}
            updates = []
            for name in ("system_a", "vendor_a", "system_ext_a", "vbmeta_a"):
                source = artifacts / f"{name}.img"
                if name == "vbmeta_a":
                    p = physical[name]
                    extents = [(p["start"] * 512, p["size"] * 512)]
                else:
                    extents = []
                    for extent in logical[name].extents:
                        if extent.target_type != LP_TARGET_TYPE_LINEAR or extent.target_source != 0:
                            raise ValueError(f"Unsupported extent in {name}")
                        offset = super_start + extent.target_data * 512
                        length = extent.num_sectors * 512
                        if offset < super_start or offset + length > super_end:
                            raise ValueError(f"Extent outside super: {name}")
                        extents.append((offset, length))
                size = source.stat().st_size
                if not size or size > sum(length for _, length in extents):
                    raise ValueError(f"{source} does not fit {name}")
                with source.open("rb") as stream:
                    expected = hashlib.file_digest(stream, "sha256").hexdigest()
                if disk_hash(disk, extents, size) != expected:
                    updates.append((name, source, extents, expected))
            for name, source, extents, expected in updates:
                print(f"Updating {name} ({source.stat().st_size >> 20} MiB)", flush=True)
                copy_component(disk, source, extents)
                if disk_hash(disk, extents, source.stat().st_size) != expected:
                    raise OSError(f"Read-back verification failed: {name}")
            print("Android OS partitions verified; userdata and metadata were not touched."
                  if updates else "Android disk is up to date; no partitions written.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("artifacts", type=Path)
    args = parser.parse_args()
    try:
        sync(args.image, args.artifacts)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"android-sync: {error}\n")


if __name__ == "__main__":
    main()
