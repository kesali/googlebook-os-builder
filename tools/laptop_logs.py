#!/usr/bin/env python3
"""Retrieve diagnostic logs; never mount or write USB devices."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

from update_usb import check_unused, choose, disks, run

LOG_NAME = re.compile(r"(?:boot-id|boot\.txt|hardware\.txt|touchpad\.log|"
                      r"(?:kernel|android|android-boot|crash)\.log(?:\.[0-9]+)?)\Z")


class LogReadError(ValueError):
    """A log or directory could not be read from the filesystem."""


def debugfs(device, request):
    result = subprocess.run(
        ["sudo", "--", "debugfs", "-R", request, str(device)],
        capture_output=True,
    )
    diagnostics = result.stderr.decode(errors="replace").splitlines()
    errors = [line for line in diagnostics if not line.startswith("debugfs ")]
    if result.returncode or errors:
        raise LogReadError(f"Cannot read USB logs ({request}): "
                           + ("\n".join(errors) or f"exit {result.returncode}"))
    return result.stdout


def directory(device, path):
    entries = {}
    for line in debugfs(device, f"ls -p {path}").decode().splitlines():
        if not line.strip():
            continue
        fields = line.split("/")
        if len(fields) != 8 or fields[0] or fields[-1]:
            raise ValueError(f"Unexpected debugfs directory listing: {line}")
        _, inode, mode, _, _, name, size, _ = fields
        if name in (".", "..") or inode == "0":
            continue
        if "/" in name or name in entries:
            raise ValueError("Invalid or duplicate USB log filename")
        entries[name] = (int(mode, 8), int(size) if size else 0)
    return entries


def log_device(selected):
    current = next((node for node in disks() if node["name"] == selected["name"]), None)
    if current is None or any(current[key] != selected[key]
                              for key in ("maj:min", "serial", "size", "model", "tran")):
        raise ValueError("Selected USB changed or disappeared; select it again")
    if current["tran"] != "usb" or not current["serial"]:
        raise ValueError("Expected a USB disk with a serial number")
    check_unused(current)
    labeled = json.loads(run(
        "lsblk", "--json", "--paths", "--output", "NAME,PARTLABEL,FSTYPE", current["name"],
    ))["blockdevices"]
    children = labeled[0].get("children", []) if len(labeled) == 1 else []
    matches = [child["name"] for child in children if child.get("partlabel") == "gbos_logs"]
    if matches:
        if len(matches) != 1:
            raise ValueError("Selected USB must have exactly one log partition")
        log_partition = next(child for child in children if child["name"] == matches[0])
        filesystem = log_partition.get("fstype")
        if filesystem != "ext4":
            raise ValueError(f"Unsupported diagnostic log filesystem: {filesystem}")
        root = ""
    else:
        # Older images stored captures on metadata; retrieval does not migrate or write them.
        matches = [child["name"] for child in children if child.get("partlabel") == "metadata"]
        if len(matches) != 1:
            raise ValueError("Selected USB must have exactly one log partition (or legacy metadata)")
        metadata = next(child for child in children if child["name"] == matches[0])
        if metadata.get("fstype") != "ext4":
            raise ValueError("Legacy metadata log partition must be ext4")
        filesystem = "ext4"
        root = "/gbos-builder-bootlog"
    device = Path(matches[0])
    child = next((node for node in current.get("children", [])
                  if node["name"] == str(device)), None)
    info = device.stat()
    if child is None or not stat.S_ISBLK(info.st_mode) or (
        f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}" != child["maj:min"]
    ):
        raise ValueError("Log device does not match the selected USB")
    return device, filesystem, root


def retrieve(selected, output):
    device, filesystem, root = log_device(selected)
    print(f"Reading {filesystem} diagnostic storage: {device}")
    boots = directory(device, root)
    if "current" in boots and not stat.S_ISDIR(boots["current"][0]):
        raise ValueError("No current boot logs; this may not be the gbos-builder Android USB")
    if "current" not in boots and "previous" not in boots:
        raise ValueError("No boot logs; this may not be the gbos-builder Android USB")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    latest = output / "latest"
    if latest.exists() and not latest.is_symlink():
        raise ValueError(f"{latest} exists and is not a symlink; refusing to replace it")
    destination = Path(tempfile.mkdtemp(
        prefix=datetime.now().strftime("%Y%m%d-%H%M%S-"), dir=output,
    ))
    total = 0
    problems = [] if "current" in boots else ["Current boot logs are missing"]
    try:
        for boot in ("current", "previous"):
            if boot not in boots:
                continue
            if not stat.S_ISDIR(boots[boot][0]):
                raise ValueError(f"USB log directory {boot} is not a directory")
            source = f"{root}/{boot}"
            try:
                entries = directory(device, source)
            except LogReadError as error:
                problems.append(str(error))
                continue
            if "boot-id" not in entries:
                problems.append(f"{boot} logs have no boot-id; boot identity is unknown")
            temporary_snapshot = entries.pop("hardware.txt.tmp", None)
            if temporary_snapshot is not None:
                mode, size = temporary_snapshot
                if not stat.S_ISREG(mode) or size > 10 << 20 or size < 0:
                    raise ValueError(f"Invalid temporary hardware snapshot: {boot}")
                print(f"Skipping unfinished {boot}/hardware.txt.tmp; "
                      "only completed hardware snapshots are retrieved.")
            for name, (mode, size) in entries.items():
                if not LOG_NAME.fullmatch(name):
                    raise ValueError(f"Unexpected USB log entry: {boot}/{name}")
                if not stat.S_ISREG(mode) or size > 10 << 20 or size < 0:
                    raise ValueError(f"Invalid log file type/size: {boot}/{name}")
            target = destination / boot
            target.mkdir(mode=0o700)
            identity = None
            if "boot-id" in entries:
                try:
                    identity = debugfs(device, f"cat {source}/boot-id")
                except LogReadError as error:
                    problems.append(str(error))
                else:
                    size = entries["boot-id"][1]
                    if len(identity) != size:
                        problems.append(f"Log changed or was unreadable: {boot}/boot-id")
                        identity = None
                    else:
                        try:
                            uuid.UUID(identity.decode().strip())
                        except (UnicodeDecodeError, ValueError):
                            problems.append(f"{boot} boot-id is invalid; boot identity is unknown")
            for name, (_, size) in entries.items():
                if name == "boot-id":
                    if identity is None:
                        continue
                    data = identity
                else:
                    try:
                        data = debugfs(device, f"cat {source}/{name}")
                    except LogReadError as error:
                        problems.append(str(error))
                        continue
                if len(data) != size:
                    problems.append(f"Log changed or was unreadable: {boot}/{name}")
                    continue
                total += len(data)
                if total > 40 << 20:
                    raise ValueError("Saved boot logs exceed the 40 MiB retrieval limit")
                (target / name).write_bytes(data)
            if identity is not None:
                try:
                    final_identity = debugfs(device, f"cat {source}/boot-id")
                except LogReadError as error:
                    problems.append(str(error))
                else:
                    if final_identity != identity:
                        raise ValueError("USB boot logs changed during retrieval; retry")
        if log_device(selected) != (device, filesystem, root):
            raise ValueError("Log partition changed during retrieval")
        if problems:
            raise ValueError("Log retrieval incomplete:\n" + "\n".join(problems))
        temporary_link = destination / "latest-link"
        temporary_link.symlink_to(destination.name)
        temporary_link.replace(latest)
    except (OSError, ValueError, subprocess.CalledProcessError):
        print(f"Retrieval incomplete; latest was not updated. Partial logs: {destination}")
        raise
    print(f"Boot logs ready: {latest / 'current'}")
    print(f"Saved copy: {destination}\nUSB was only read; nothing mounted or written.")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if os.geteuid() == 0:
            raise ValueError("Run make laptop-logs as your normal user; only log readers use sudo")
        for tool in ("sudo", "lsblk"):
            if shutil.which(tool) is None:
                raise ValueError(f"Missing host command: {tool}")
        output = args.output.resolve()
        allowed = Path(__file__).resolve().parents[1] / "out"
        if not output.is_relative_to(allowed) or output == allowed:
            raise ValueError("Log destination must be a directory inside the repository's out/")
        selected = choose()
        if selected is None:
            print("Cancelled; nothing read.")
            return
        retrieve(selected, output)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"laptop-logs: {error}\n")
    except (EOFError, KeyboardInterrupt):
        parser.exit(1, "\nlaptop-logs: cancelled; USB was not written\n")


if __name__ == "__main__":
    main()
