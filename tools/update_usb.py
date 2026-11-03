#!/usr/bin/env python3
"""Interactively update an existing Dali Android USB, never format it or change its data/layout.

Run on the Linux host as root, after building the image. Only USB disks are offered; the image's
GPT and liblp layout must match, except that target userdata may be larger. Boot files use the
same menu-last installer as deploy.py. No disk is selected or written without confirmation.
"""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from android_layout import validate_gpt_table, validate_super_extents
from android_sync import CHUNK, disk_hash
from deploy import FORMATS, install, read_bundle
from lp import read_partitions

OS_PARTITIONS = ("system_a", "vendor_a", "system_ext_a", "vendor_dlkm_a", "vbmeta_a")
BLKSSZGET = 0x1268
BLKFLSBUF = 0x1261


def run(*args):
    return subprocess.check_output(args, text=True)


def disks():
    return json.loads(run(
        "lsblk", "--json", "--bytes", "--paths",
        "--output", "NAME,TYPE,TRAN,SIZE,MODEL,SERIAL,RO,MAJ:MIN,MOUNTPOINTS",
    ))["blockdevices"]


def usb_disks(nodes):
    return [node for node in nodes if node["type"] == "disk" and node["tran"] == "usb"]


def check_unused(node):
    """Include swap, partition mounts and device-mapper/RAID holders, not just the disk itself."""
    for mount in node.get("mountpoints") or []:
        if mount:
            raise ValueError(f"{node['name']} is in use at {mount}; unmount it first")
    holders = Path("/sys/dev/block") / node["maj:min"] / "holders"
    if any(holders.iterdir()):
        raise ValueError(f"{node['name']} has active device holders")
    for child in node.get("children", []):
        check_unused(child)


def check_identity(selected, stream):
    current = next((node for node in usb_disks(disks())
                    if node["name"] == selected["name"]), None)
    if current is None or any(current[key] != selected[key]
                              for key in ("maj:min", "serial", "size", "model")):
        raise ValueError("Selected USB changed or disappeared; select it again")
    info = os.fstat(stream.fileno())
    if not stat.S_ISBLK(info.st_mode) or (
        f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}" != selected["maj:min"]
    ):
        raise ValueError("Selected USB no longer matches the open device")
    if current["ro"]:
        raise ValueError("Selected USB is read-only")
    return current


def table(path):
    return validate_gpt_table(json.loads(run("sfdisk", "--json", str(path)))["partitiontable"])


def verify_gpt(path):
    result = subprocess.run(["sfdisk", "--verify", str(path)],
                            check=False, capture_output=True, text=True)
    # Some util-linux versions report GPT errors on stderr but still exit zero.
    if result.returncode or result.stderr.strip():
        diagnostics = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"GPT verification failed for {path} "
                         f"(status {result.returncode}):\n{diagnostics}")
    print(result.stdout, end="", flush=True)


def verify_target_gpt(source, target, source_table, path, target_size):
    """Verify normally, or match both GPT copies to the already verified source image."""
    source_size = os.fstat(source.fileno()).st_size
    if target_size > source_size:
        first = source_table["firstlba"] * 512
        end = (source_table["lastlba"] + 1) * 512
        if not 1024 <= first < end < source_size:
            raise ValueError("Invalid source GPT metadata bounds")
        # A verbatim flash leaves backup GPT at the image boundary, not the USB end.
        # Match all metadata bytes, including PMBR, headers and partition-array CRCs;
        # never accept a damaged or changed copy merely because sfdisk can read it.
        ranges = [(0, first), (end, source_size - end)]
        length = sum(size for _, size in ranges)
        if disk_hash(source, ranges, length) == disk_hash(target, ranges, length):
            print("USB GPT matches the verified image exactly; backup remains at the "
                  "image boundary. No GPT changes needed.", flush=True)
            return
    verify_gpt(path)


def check_layout(source, target):
    for key in ("id", "firstlba"):
        if source[key] != target[key]:
            raise ValueError(f"USB GPT {key} differs from the built image")
    expected = source["partitions"]
    actual = target["partitions"]
    if len(expected) != len(actual):
        raise ValueError("USB has a different number of GPT partitions")
    for before, after in zip(expected, actual):
        before = {key: value for key, value in before.items() if key != "node"}
        after = {key: value for key, value in after.items() if key != "node"}
        if before["name"] == "userdata":
            if after["size"] < before["size"]:
                raise ValueError("USB userdata is smaller than the built image")
            after["size"] = before["size"]
        if before != after:
            raise ValueError(f"USB GPT partition differs: {before['name']}")


def os_extents(stream, layout):
    physical = {entry["name"]: entry for entry in layout["partitions"]}
    super_start = physical["super"]["start"] * 512
    super_end = super_start + physical["super"]["size"] * 512
    partitions = read_partitions(stream, super_start)
    logical, metadata = validate_super_extents(stream, super_start, super_end, partitions)
    ranges = {}
    for name in OS_PARTITIONS:
        if name == "vbmeta_a":
            part = physical[name]
            ranges[name] = [(part["start"] * 512, part["size"] * 512)]
        else:
            ranges[name] = logical[name]
        if not ranges[name]:
            raise ValueError(f"No extents for {name}")
    return ranges, metadata


def plan_os(source, target, ranges, metadata):
    offset, length = metadata
    if disk_hash(source, [(offset, length)], length) != disk_hash(target, [(offset, length)], length):
        raise ValueError("USB super metadata differs; this tool cannot reflash or repartition it")
    updates = []
    for name, extents in ranges.items():
        length = sum(size for _, size in extents)
        expected = disk_hash(source, extents, length)
        if disk_hash(target, extents, length) != expected:
            updates.append((name, extents, expected))
    return updates


def write_os(source, target, updates, before_write, flush):
    for name, extents, expected in updates:
        before_write()
        print(f"{name}: writing {sum(size for _, size in extents) >> 20} MiB", flush=True)
        for offset, length in extents:
            source.seek(offset)
            target.seek(offset)
            while length:
                data = source.read(min(length, CHUNK))
                if not data:
                    raise ValueError(f"Image ends inside {name}")
                if target.write(data) != len(data):
                    raise OSError(f"Short write updating {name}")
                length -= len(data)
        target.flush()
        os.fsync(target.fileno())
        flush()
        length = sum(size for _, size in extents)
        if disk_hash(target, extents, length) != expected:
            raise OSError(f"USB read-back differs: {name}")
        print(f"{name}: read-back verified", flush=True)


@contextmanager
def boot_mount(device, writable=False):
    directory = Path(tempfile.mkdtemp(prefix="dali-update-mount-", dir="/run"))
    options = "rw" if writable else "ro"
    mounted = False
    try:
        subprocess.run(["mount", "-t", "vfat", "-o", options + ",nodev,nosuid,noexec",
                        str(device), str(directory)], check=True)
        mounted = True
        yield directory
    finally:
        if mounted:
            subprocess.run(["umount", str(directory)], check=True)
        # Never recursively clean a mountpoint: a failed unmount must leave it untouched.
        directory.rmdir()


@contextmanager
def snapshot_bundle(bundle):
    kind, files, hashes = read_bundle(bundle)
    if kind != "android":
        raise ValueError("Expected an Android boot bundle")
    with tempfile.TemporaryDirectory(prefix="dali-update-bundle-", dir="/run") as temporary:
        destination = Path(temporary)
        for name, data in files.items():
            (destination / name).write_bytes(data)
        (destination / "manifest.json").write_text(json.dumps({"kind": kind, "sha256": hashes}))
        yield destination


def choose():
    candidates = usb_disks(disks())
    if not candidates:
        raise ValueError("No USB disks connected")
    for index, node in enumerate(candidates, 1):
        print(f"{index}. {node['name']}  {node['size'] / (1 << 30):.1f} GiB  "
              f"{node['model']}  serial={node['serial'] or '(missing)'}"
              f"{' [read-only]' if node['ro'] else ''}")
    choice = input("USB number (Enter cancels): ").strip()
    if not choice:
        return None
    if not choice.isdecimal() or not 1 <= int(choice) <= len(candidates):
        raise ValueError("Invalid USB selection")
    return candidates[int(choice) - 1]


def update(image, bundle):
    if os.geteuid() != 0:
        raise ValueError("Run through make update-usb (requires sudo)")
    for name in ("lsblk", "sfdisk", "mount", "umount"):
        if shutil.which(name) is None:
            raise ValueError(f"Missing host command: {name}")
    if image.is_symlink() or not stat.S_ISREG(image.stat().st_mode):
        raise ValueError("Source must be a regular built image, not a symlink/device")
    with Path(str(image) + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Stop QEMU or other image updates first") from error
        selected = choose()
        if selected is None:
            print("Cancelled; nothing written.")
            return
        if not selected["serial"]:
            raise ValueError("Selected USB has no serial number; cannot verify its identity")
        path = Path(selected["name"])
        if path.is_symlink() or not stat.S_ISBLK(path.stat().st_mode):
            raise ValueError("Selected target is not a real block device")
        # An exclusive BSD lock also prevents systemd-udevd probing the disk during the update.
        with os.fdopen(os.open(image, os.O_RDONLY | os.O_NOFOLLOW), "rb", buffering=0) as source, \
                os.fdopen(os.open(path, os.O_RDWR | os.O_NOFOLLOW), "r+b", buffering=0) as target, \
                snapshot_bundle(bundle) as frozen_bundle:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError("Source is no longer a regular image")
            fcntl.flock(target, fcntl.LOCK_EX | fcntl.LOCK_NB)

            def unused():
                check_unused(check_identity(selected, target))

            unused()
            sector_size = int.from_bytes(fcntl.ioctl(target, BLKSSZGET, bytes(4)), "little")
            if sector_size != 512:
                raise ValueError("USB logical sectors must be 512 bytes")
            print("Checking USB layout and comparing OS partitions (read-only)...", flush=True)
            source_table, target_table = table(image), table(path)
            verify_gpt(image)
            verify_target_gpt(source, target, source_table, path, selected["size"])
            check_layout(source_table, target_table)
            ranges, metadata = os_extents(source, source_table)
            planned = plan_os(source, target, ranges, metadata)
            esp = {part["name"]: part for part in target_table["partitions"]}["EFI-SYSTEM"]
            boot_device = Path(esp["node"])
            if not any(child["name"] == str(boot_device)
                       for child in selected.get("children", [])):
                raise ValueError("Boot partition is not a child of the selected USB")
            target.seek(esp["start"] * 512)
            boot_sector = target.read(512)
            if boot_sector[71:82] != b"DALI-BOOT  " or boot_sector[82:90] != b"FAT32   ":
                raise ValueError("USB EFI-SYSTEM is not the DALI-BOOT FAT32 filesystem")
            unused()
            with boot_mount(boot_device) as mountpoint:
                if (mountpoint / "dali/format").read_bytes() != FORMATS["android"]:
                    raise ValueError("USB does not have the Dali Android boot marker")
                boot_changes = install(frozen_bundle, mountpoint, dry_run=True)
            print("OS updates: " + (", ".join(name for name, _, _ in planned) or "none"))
            print("Boot updates: " + (", ".join(boot_changes) or "none"))
            print("Userdata, metadata and partition tables will not be written.")
            if not planned and not boot_changes:
                print("USB is already up to date; nothing written.")
                return
            confirmation = input(
                f"Write updates to {path} ({selected['model']}, {selected['serial']})? [y/N] "
            ).strip().lower()
            if confirmation not in ("y", "yes"):
                print("Cancelled; nothing written.")
                return
            unused()
            # Revalidate the layout and hashes after the user prompt, before the first write.
            check_layout(source_table, table(path))
            if plan_os(source, target, ranges, metadata) != planned:
                raise ValueError("USB contents changed while waiting for confirmation; rerun")
            write_os(source, target, planned, unused,
                     lambda: fcntl.ioctl(target, BLKFLSBUF))
            unused()
            if boot_changes:
                with boot_mount(boot_device, writable=True) as mountpoint:
                    for name in install(frozen_bundle, mountpoint):
                        print(f"Boot updated: {name}")
                fcntl.ioctl(target, BLKFLSBUF)
                with boot_mount(boot_device) as mountpoint:
                    if install(frozen_bundle, mountpoint, dry_run=True):
                        raise OSError("Boot files differ after remount/read-back")
            unused()
            print("USB update verified. Data preserved; safely unplug before booting.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        update(args.image, args.bundle)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"update-usb: {error}\n")
    except (EOFError, KeyboardInterrupt):
        parser.exit(1, "\nupdate-usb: interrupted; rerun to repair a partial update\n")


if __name__ == "__main__":
    main()
