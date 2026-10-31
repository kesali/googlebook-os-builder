#!/usr/bin/env python3
"""Publish a build bundle or update the boot filesystem of a mounted Dali USB.

New kernel/initramfs files are content-addressed. The menu switches last, after
read-back verification. No partition table, other partition, or user file is edited.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

FORMAT = b"gbos-dali-diagnostic-v1\n"
COMPONENTS = ("kernel", "initramfs.gz", "BOOTX64.EFI", "menu.cfg")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(root, relative):
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError(f"Unsafe destination: {relative}")
    for item in (path, *path.parents):
        if item == root:
            break
        if item.is_symlink():
            raise ValueError(f"Refusing symlink: {item}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Not a regular file: {path}")
    return path


def replace_file(root, relative, data):
    """Atomic rename on a mounted filesystem; rehash actual bytes, not cached metadata."""
    path = safe_path(root, relative)
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".dali-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != data:
            raise OSError(f"Read-back verification failed: {relative}")
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def bundle(inputs, destination):
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, source in zip(COMPONENTS, inputs, strict=True):
        data = source.read_bytes()
        if not data:
            raise ValueError(f"Empty build output: {source}")
        replace_file(destination, name, data)
        hashes[name] = digest(data)
    manifest = json.dumps(hashes, sort_keys=True, indent=2).encode() + b"\n"
    replace_file(destination, "manifest.json", manifest)


def read_bundle(source):
    hashes = json.loads((source / "manifest.json").read_text())
    if set(hashes) != set(COMPONENTS):
        raise ValueError("Invalid build bundle manifest")
    files = {name: (source / name).read_bytes() for name in COMPONENTS}
    for name, data in files.items():
        if not data or digest(data) != hashes[name]:
            raise ValueError(f"Build bundle checksum mismatch: {name}")
    return files, hashes


def install(source, destination, initialize=False):
    files, hashes = read_bundle(source)
    destination = destination.absolute()
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("Destination must be a real directory")
    marker = safe_path(destination, "dali/format")
    if initialize:
        if any(destination.iterdir()):
            raise ValueError("Image staging directory must be empty")
    elif not marker.is_file() or marker.read_bytes() != FORMAT:
        raise ValueError("Not a Dali diagnostic USB; create and flash an image first")

    kernel = f"dali/kernel-{hashes['kernel']}"
    initramfs = f"dali/initramfs-{hashes['initramfs.gz']}"
    menu = files["menu.cfg"].replace(b"@KERNEL@", hashes["kernel"].encode())
    menu = menu.replace(b"@INITRAMFS@", hashes["initramfs.gz"].encode())
    payloads = {
        kernel: files["kernel"],
        initramfs: files["initramfs.gz"],
        "EFI/BOOT/BOOTX64.EFI": files["BOOTX64.EFI"],
        "dali/format": FORMAT,
    }
    # Check all destinations and available space before writing the first byte.
    for name in (*payloads, "dali/grub.cfg", "dali/grub.previous.cfg"):
        safe_path(destination, name)
    current = destination / "dali/grub.cfg"
    menu_changed = not current.exists() or current.read_bytes() != menu
    required = sum(
        len(data) for name, data in payloads.items()
        if not (destination / name).exists() or (destination / name).read_bytes() != data
    )
    if not required and not menu_changed:
        return []
    required += 2 * len(menu) + (1 << 20)
    space = os.statvfs(destination)
    if required > space.f_bavail * space.f_frsize:
        raise OSError("Not enough free space on the boot filesystem (old builds are retained)")

    changed = []
    for name, data in payloads.items():
        if replace_file(destination, name, data):
            changed.append(name)
    if current.is_file() and current.read_bytes() != menu:
        replace_file(destination, "dali/grub.previous.cfg", current.read_bytes())
    if replace_file(destination, "dali/grub.cfg", menu):
        changed.append("dali/grub.cfg")
    return changed


def verify_usb_mount(path):
    if path.is_symlink() or path.absolute() != path.resolve() or path.resolve() == Path("/"):
        raise ValueError("Use the real USB mountpoint, not a symlink or /")
    result = subprocess.run(
        ["findmnt", "--json", "--mountpoint", str(path), "--output", "TARGET,SOURCE,FSTYPE,OPTIONS"],
        check=True, capture_output=True, text=True,
    )
    mounts = json.loads(result.stdout)["filesystems"]
    if len(mounts) != 1:
        raise ValueError("Expected exactly one mounted filesystem")
    mount = mounts[0]
    if Path(mount["target"]).resolve() != path.resolve():
        raise ValueError("Destination is not the filesystem mountpoint")
    if mount["fstype"] != "vfat" or "rw" not in mount["options"].split(","):
        raise ValueError("USB boot partition must be mounted read-write as vfat")
    device = Path(mount["source"])
    if not stat.S_ISBLK(device.stat().st_mode):
        raise ValueError("Mounted source is not a block device")
    result = subprocess.run(
        ["lsblk", "--json", "--inverse", "--output", "TRAN,TYPE", str(device)],
        check=True, capture_output=True, text=True,
    )

    def usb_disk(nodes):
        return any(
            (node.get("tran") == "usb" and node.get("type") == "disk")
            or usb_disk(node.get("children", []))
            for node in nodes
        )

    if not usb_disk(json.loads(result.stdout)["blockdevices"]):
        raise ValueError("Destination is not on a USB disk; internal disks are not supported")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("bundle")
    prepare.add_argument("inputs", nargs=4, type=Path, metavar="FILE")
    prepare.add_argument("destination", type=Path)
    stage = sub.add_parser("stage", help="populate a NEW empty image staging directory")
    stage.add_argument("bundle", type=Path)
    stage.add_argument("destination", type=Path)
    deploy = sub.add_parser("usb", help="update an already-mounted USB boot partition")
    deploy.add_argument("bundle", type=Path)
    deploy.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "bundle":
            bundle(args.inputs, args.destination)
        else:
            if args.command == "usb":
                verify_usb_mount(args.destination)
            changed = install(args.bundle, args.destination, initialize=args.command == "stage")
            print("\n".join(f"updated {name}" for name in changed) if changed else "Already up to date; no files written.")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"deploy: {error}\n")


if __name__ == "__main__":
    main()
