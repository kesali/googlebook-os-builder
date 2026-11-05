#!/usr/bin/env python3
"""Flash a built Android image to an explicitly selected USB, erasing its data.

Host-only, owner-run operation. Never offer internal disks or select a default.
Verify the full image copy, then initialize fresh Android data and expand trailing userdata.
Never resize a live filesystem or change an existing USB through the update command.
"""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

from android_sync import CHUNK, disk_hash
from android_disk import PARTITIONS
from android_layout import validate_gpt_table
from update_usb import (
    BLKFLSBUF, BLKSSZGET, check_identity, check_unused, choose, os_extents, table,
    check_layout, verify_gpt,
)


def check_capacity(node, size):
    if not node["serial"] or not node["serial"].strip():
        raise ValueError("Selected USB has no serial number; cannot verify its identity")
    if node["ro"]:
        raise ValueError("Selected USB is read-only")
    if node["size"] < size:
        raise ValueError(f"USB is too small: needs at least {size} bytes")


def flash(source, target, size, expected, before_write, flush):
    """Write and verify only the image range; usable with regular-file test fixtures."""
    source.seek(0)
    target.seek(0)
    remaining = size
    written = hashlib.sha256()
    before_write()
    while remaining:
        data = source.read(min(remaining, CHUNK))
        if not data:
            raise ValueError("Source image ended during flashing")
        if target.write(data) != len(data):
            raise OSError("Short write flashing USB")
        written.update(data)
        remaining -= len(data)
    target.flush()
    os.fsync(target.fileno())
    flush()
    if written.hexdigest() != expected:
        raise ValueError("Source image changed during flashing; do not boot this USB")
    before_write()
    print("Full image written; verifying USB read-back...", flush=True)
    if disk_hash(target, [(0, size)], size) != expected:
        raise OSError("USB read-back differs; do not boot it")


def data_layout(source_table, source_size, target_size):
    parts = source_table["partitions"]
    if tuple(part["name"] for part in parts) != PARTITIONS:
        raise ValueError("Fresh installation requires the compact image; rebuild before flashing")
    for number, part in enumerate(parts, 1):
        suffix = re.search(r"(\d+)$", part.get("node", ""))
        if suffix is None or int(suffix[1]) != number:
            raise ValueError("Compact image partition numbers must be contiguous")
    if target_size < source_size or target_size % 512:
        raise ValueError("USB capacity must fit the image and use whole sectors")
    data = parts[-1]
    metadata = next(part for part in parts if part["name"] == "metadata")
    backup_sectors = source_size // 512 - source_table["lastlba"] - 1
    if not 33 <= backup_sectors <= 2048:
        raise ValueError("Unexpected GPT backup reservation")
    ordered = sorted(parts, key=lambda part: part["start"])
    for index, part in enumerate(ordered):
        if part["start"] < source_table["firstlba"] or part["size"] <= 0 or (
                part["start"] + part["size"] > source_table["lastlba"] + 1):
            raise ValueError(f"Partition outside image: {part['name']}")
        if index and ordered[index - 1]["start"] + ordered[index - 1]["size"] > part["start"]:
            raise ValueError("Overlapping source partitions")
    if ordered[-1]["name"] != "userdata" or data["size"] * 512 < 1 << 20:
        raise ValueError("Userdata must be last and at least 1 MiB")
    if metadata["size"] * 512 < 1 << 20:
        raise ValueError("Metadata must be at least 1 MiB")
    sectors = target_size // 512 - backup_sectors - data["start"]
    if sectors < data["size"]:
        raise ValueError("USB has no room for the original userdata allocation")
    return data, metadata, sectors


def initialize_data(source_table, source_size, target, target_size, before_write, flush):
    """Fresh-install only: discard copied encryption state, then grow unformatted userdata."""
    data, metadata, sectors = data_layout(source_table, source_size, target_size)
    for name, offset, length in (
            ("metadata", metadata["start"] * 512, metadata["size"] * 512),
            ("userdata signature", data["start"] * 512, 1 << 20)):
        before_write()
        target.seek(offset)
        remaining = length
        while remaining:
            block = bytes(min(CHUNK, remaining))
            if target.write(block) != len(block):
                raise OSError(f"Short write resetting {name}")
            remaining -= len(block)
        target.flush()
        os.fsync(target.fileno())
        flush()
        target.seek(offset)
        remaining = length
        while remaining:
            count = min(CHUNK, remaining)
            if target.read(count) != bytes(count):
                raise OSError(f"Read-back differs resetting {name}")
            remaining -= count
    # Address the already locked descriptor, not a path that could name a different device.
    device = f"/proc/self/fd/{target.fileno()}"
    before_write()
    subprocess.run(["sfdisk", "--quiet", "--no-reread", "--relocate", "gpt-bak-std", device],
                   pass_fds=(target.fileno(),), check=True)
    before_write()
    subprocess.run(["sfdisk", "--quiet", "--no-reread", "-N", str(len(PARTITIONS)), device],
                   input=f"{data['start']},{sectors}\n", text=True,
                   pass_fds=(target.fileno(),), check=True)
    os.fsync(target.fileno())
    flush()
    before_write()
    result = subprocess.run(["sfdisk", "--json", device], pass_fds=(target.fileno(),),
                            check=True, capture_output=True, text=True)
    actual = validate_gpt_table(json.loads(result.stdout)["partitiontable"])
    check_layout(source_table, actual)
    grown = next(part for part in actual["partitions"] if part["name"] == "userdata")
    if grown["size"] != sectors or actual["lastlba"] != data["start"] + sectors - 1:
        raise OSError("Expanded userdata/GPT read-back differs")
    verified = subprocess.run(["sfdisk", "--verify", device], pass_fds=(target.fileno(),),
                              capture_output=True, text=True, check=False)
    if verified.returncode or verified.stderr.strip():
        raise ValueError(f"Expanded GPT verification failed:\n{verified.stderr or verified.stdout}")
    print(f"Fresh userdata uses {sectors * 512 / (1 << 30):.1f} GiB; "
          "Android will format it on first boot.", flush=True)


def install(image):
    if os.geteuid() != 0:
        raise ValueError("Run through make install-usb (requires sudo)")
    for name in ("lsblk", "sfdisk"):
        if shutil.which(name) is None:
            raise ValueError(f"Missing host command: {name}")
    if image.is_symlink() or not image.is_file():
        raise ValueError("Source must be a regular built image, never a symlink/device")
    with Path(str(image) + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with os.fdopen(os.open(image, os.O_RDONLY | os.O_NOFOLLOW), "rb", buffering=0) as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or not info.st_size or info.st_size % 512:
                raise ValueError("Expected a nonempty, sector-aligned regular image")
            source_table = table(image)
            verify_gpt(image)
            os_extents(source, source_table)
            data_layout(source_table, info.st_size, info.st_size)
            selected = choose()
            if selected is None:
                print("Cancelled; nothing written.")
                return
            check_capacity(selected, info.st_size)
            check_unused(selected)
            path = Path(selected["name"])
            if path.is_symlink() or not stat.S_ISBLK(path.stat().st_mode):
                raise ValueError("Selected target is not a real block device")
            with os.fdopen(os.open(path, os.O_RDWR | os.O_NOFOLLOW),
                           "r+b", buffering=0) as target:
                fcntl.flock(target, fcntl.LOCK_EX | fcntl.LOCK_NB)

                def unused():
                    current = check_identity(selected, target)
                    check_capacity(current, info.st_size)
                    check_unused(current)

                unused()
                sector_size = int.from_bytes(fcntl.ioctl(target, BLKSSZGET, bytes(4)), "little")
                if sector_size != 512:
                    raise ValueError("USB logical sectors must be 512 bytes")
                source.seek(0)
                expected = hashlib.file_digest(source, "sha256").hexdigest()
                print(f"ERASE {path}: {selected['model']}, serial={selected['serial']}, "
                      f"{selected['size'] / (1 << 30):.1f} GiB")
                print(f"Source: {image} ({info.st_size} bytes)")
                print("ALL existing USB accounts, apps, files and partitions will be lost.")
                print("Copied Android data/encryption state is reset; userdata fills remaining USB space.")
                answer = input(f"Type ERASE {selected['serial']} to flash, or Enter to cancel: ")
                if answer != f"ERASE {selected['serial']}":
                    print("Cancelled; nothing written.")
                    return
                unused()
                after = os.fstat(source.fileno())
                if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
                        info.st_size, info.st_mtime_ns, info.st_ctime_ns):
                    raise ValueError("Source changed while awaiting confirmation; rebuild first")
                flash(source, target, info.st_size, expected, unused,
                      lambda: fcntl.ioctl(target, BLKFLSBUF))
                initialize_data(source_table, info.st_size, target, selected["size"], unused,
                                lambda: fcntl.ioctl(target, BLKFLSBUF))
                print("Fresh USB image verified. Safely unplug/replug before booting.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    try:
        install(args.image)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"install-usb: {error}\n")
    except (EOFError, KeyboardInterrupt):
        parser.exit(1, "\ninstall-usb: interrupted; USB may be incomplete. Rerun before booting.\n")


if __name__ == "__main__":
    main()
