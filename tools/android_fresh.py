#!/usr/bin/env python3
"""Create a new private Android disk with the enlarged super layout.

Read only Google's recovery and built artifacts. Never overwrite an existing
output, the old working disk or a physical device.
"""

import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from android_layout import load_allocations, validate_gpt_table
from android_sync import copy_component, disk_hash, sync
from super_candidate import build, image_digest, regular_file


OUT = Path(__file__).resolve().parents[1] / "out"


def check_output(output):
    if output.exists() or output.is_symlink():
        raise ValueError(f"Refusing to replace {output}")
    if not output.resolve().is_relative_to(OUT):
        raise ValueError("Fresh disks must stay under the repository's out/")
    if output.resolve() == OUT / "android/disk.img":
        raise ValueError("Preserve the old working Android disk")


def create(lpmake, recovery, google, artifacts, layout_path, userdata_gib, output):
    check_output(output)
    regular_file(recovery)
    regular_file(lpmake)
    allocations = load_allocations(layout_path)
    if userdata_gib < 1:
        raise ValueError("Userdata must be at least 1 GiB")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fresh.partial.", dir=output.parent) as temporary:
        work = Path(temporary)
        images = work / "images"
        images.mkdir()
        for name in allocations:
            source = (google / "super" if name in ("product_a", "system_dlkm_a")
                      else artifacts) / f"{name}.img"
            regular_file(source)
            subprocess.run(["cp", "--reflink=auto", "--sparse=always",
                            str(source), str(images / source.name)], check=True)
        super_image = work / "super.img"
        build(lpmake, recovery, images, images / "vendor_dlkm_a.img", super_image, allocations)
        disk = work / "disk.img"
        subprocess.run(["bash", "scripts/android-disk.sh", str(recovery),
                        str(userdata_gib), str(disk)], check=True)
        table = validate_gpt_table(json.loads(subprocess.check_output(
            ["sfdisk", "--json", str(disk)], text=True))["partitiontable"])
        super_entries = [p for p in table["partitions"] if p["name"] == "super"]
        if len(super_entries) != 1:
            raise ValueError("Expected exactly one super partition in the fresh disk")
        entry = super_entries[0]
        extents = [(entry["start"] * 512, entry["size"] * 512)]
        if super_image.stat().st_size != extents[0][1]:
            raise ValueError("Generated super does not match the fresh GPT allocation")
        with disk.open("r+b") as stream:
            copy_component(stream, super_image, extents)
            if disk_hash(stream, extents, super_image.stat().st_size) != image_digest(super_image):
                raise ValueError("Fresh super read-back differs")
        sync(disk, artifacts, allocations)
        subprocess.run(["bash", "scripts/android-boot.sh", str(disk),
                        str(artifacts / "boot")], check=True)
        subprocess.run(["sfdisk", "--verify", str(disk)], check=True)
        disk.chmod(0o600)
        with disk.open("rb") as stream:
            os.fsync(stream.fileno())
        output.hardlink_to(disk)
        directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    print(f"Fresh Android disk ready: {output}; old disk untouched. "
          "Flashing this image erases the selected USB.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("lpmake", "recovery", "google", "artifacts", "layout"):
        parser.add_argument(name, type=Path)
    parser.add_argument("userdata_gib", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        create(args.lpmake, args.recovery, args.google, args.artifacts,
               args.layout, args.userdata_gib, args.output)
    except (OSError, ValueError, KeyError, struct.error,
            subprocess.CalledProcessError) as error:
        parser.exit(1, f"fresh Android image: {error}\n")


if __name__ == "__main__":
    main()
