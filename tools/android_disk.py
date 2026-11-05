"""Create a compact, fresh Android GPT image; never replace an existing disk or write devices."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

from android_layout import validate_gpt_table
from android_sync import CHUNK, disk_hash
from super_candidate import regular_file
from update_usb import verify_gpt


SECTOR = 512
ALIGNMENT = 1 << 20
ESP_BYTES = 576 << 20
SUPER_BYTES = 12 << 30
LOG_BYTES = 256 << 20
LOG_PARTITION = "gbos_logs"
# The fstab needs the A boot images and misc. Keep small persistent/security partitions
# intact, and vbmeta_b for Google's GPT-based boot-control HAL, not a second OS slot.
PARTITIONS = (
    "EFI-SYSTEM", "super", "boot_a", "init_boot_a", "vendor_boot_a",
    "vbmeta_a", "vbmeta_b", "misc", "metadata",
    "desktop_security_persist", "desktop_security_storage", "frp_persist",
    LOG_PARTITION, "userdata",
)


def compact_layout(original, userdata_gib):
    if type(userdata_gib) is not int or userdata_gib < 1:
        raise ValueError("Userdata must be a positive number of GiB")
    originals = {part["name"]: part for part in original["partitions"]}
    if not (set(PARTITIONS) - {LOG_PARTITION}) <= originals.keys():
        raise ValueError("Google's recovery is missing a required compact-layout partition")
    if originals["super"]["size"] * SECTOR != SUPER_BYTES:
        raise ValueError("Expected Google's 12 GiB super partition")
    result = []
    offset = ALIGNMENT
    for name in PARTITIONS:
        if name == LOG_PARTITION:
            part = {
                "name": name, "size": LOG_BYTES // SECTOR,
                "type": "EBD0A0A2-B9E5-4433-87C0-68B6B72699C7",
                "uuid": str(uuid.uuid5(uuid.UUID(original["id"]), LOG_PARTITION)),
            }
        else:
            part = {key: value for key, value in originals[name].items() if key != "node"}
        size = part["size"] * SECTOR
        if name == "EFI-SYSTEM":
            size = ESP_BYTES
        elif name == "userdata":
            size = userdata_gib << 30
        if size <= 0 or size % SECTOR:
            raise ValueError(f"Invalid source partition size: {name}")
        part.update(start=offset // SECTOR, size=size // SECTOR)
        if name == "vbmeta_a":
            part["attrs"] = "GUID:48,49,50,51,56"
        elif name == "vbmeta_b":
            part.pop("attrs", None)
        result.append(part)
        offset = (offset + size + ALIGNMENT - 1) // ALIGNMENT * ALIGNMENT
    return result, offset + ALIGNMENT


def create(recovery, userdata_gib, output):
    regular_file(recovery)
    if output.exists() or output.is_symlink():
        raise ValueError(f"Refusing to replace {output}; preserve Android's data")
    source_table = validate_gpt_table(json.loads(subprocess.check_output(
        ["sfdisk", "--json", str(recovery)], text=True))["partitiontable"])
    verify_gpt(recovery)
    parts, size = compact_layout(source_table, userdata_gib)
    source_size = recovery.stat().st_size
    for part in source_table["partitions"]:
        if part["start"] <= 0 or part["size"] <= 0 or (
                part["start"] + part["size"]) * SECTOR > source_size:
            raise ValueError(f"Source partition outside recovery: {part['name']}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=output.name + ".partial.", dir=output.parent) as temporary:
        disk = Path(temporary) / "disk.img"
        with disk.open("xb") as target:
            disk.chmod(0o600)
            target.truncate(size)
        lines = ["label: gpt", f"label-id: {source_table['id']}"]
        for part in parts:
            line = (f"start={part['start']}, size={part['size']}, type={part['type']}, "
                    f"uuid={part['uuid']}, name=\"{part['name']}\"")
            if part.get("attrs"):
                line += f", attrs=\"{part['attrs']}\""
            lines.append(line)
        subprocess.run(["sfdisk", "--quiet", "--no-reread", str(disk)],
                       input="\n".join(lines) + "\n", text=True, check=True)
        originals = {part["name"]: part for part in source_table["partitions"]}
        with recovery.open("rb") as source, disk.open("r+b") as target:
            for part in parts:
                # super is filled by android_fresh; data and metadata start unformatted.
                if part["name"] in ("EFI-SYSTEM", "super", "userdata", "metadata", LOG_PARTITION):
                    continue
                original = originals[part["name"]]
                source.seek(original["start"] * SECTOR)
                target.seek(part["start"] * SECTOR)
                remaining = part["size"] * SECTOR
                while remaining:
                    data = source.read(min(CHUNK, remaining))
                    if not data:
                        raise ValueError(f"Truncated source partition: {part['name']}")
                    if target.write(data) != len(data):
                        raise OSError(f"Short partition write: {part['name']}")
                    remaining -= len(data)
                target.flush()
                length = part["size"] * SECTOR
                if disk_hash(source, [(original["start"] * SECTOR, length)], length) != disk_hash(
                        target, [(part["start"] * SECTOR, length)], length):
                    raise OSError(f"Partition read-back differs: {part['name']}")
            os.fsync(target.fileno())
        for name, label, cluster_sectors in (
                ("EFI-SYSTEM", "GBOS-BOOT", "8"), (LOG_PARTITION, "GBOS-LOGS", "1")):
            part = next(part for part in parts if part["name"] == name)
            subprocess.run(["mkfs.vfat", "-F", "32", "-s", cluster_sectors, "-n", label,
                            "--offset", str(part["start"]), str(disk), str(part["size"] // 2)],
                           check=True)
        verify_gpt(disk)
        with disk.open("rb") as stream:
            os.fsync(stream.fileno())
        output.hardlink_to(disk)
        directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    print(f"Compact disk ready: {output}; {len(parts)} GPT partitions, fresh userdata/metadata")
