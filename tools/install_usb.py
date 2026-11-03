#!/usr/bin/env python3
"""Flash a built Android image to an explicitly selected USB, erasing its data.

Host-only, owner-run operation. Never offer internal disks or select a default.
Copy the full image verbatim, verify read-back, and do not grow any partitions.
"""

import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess

from android_sync import CHUNK, disk_hash
from update_usb import (
    BLKFLSBUF, BLKSSZGET, check_identity, check_unused, choose, os_extents, table,
    verify_gpt, verify_target_gpt,
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
            names = {entry["name"] for entry in source_table["partitions"]}
            if not {"userdata", "metadata", "EFI-SYSTEM"} <= names:
                raise ValueError("Expected the Android image, not the diagnostic USB image")
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
                print("Partitions are not grown; space beyond the image remains unused.")
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
                unused()
                verify_target_gpt(source, target, source_table, path, selected["size"])
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
