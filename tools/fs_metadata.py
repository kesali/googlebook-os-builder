#!/usr/bin/env python3
"""Verify EROFS reconstruction preserves every file's bytes, mode, owner and xattrs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat


def snapshot(root):
    entries = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.lstat()
        item = {
            "mode": info.st_mode, "uid": info.st_uid, "gid": info.st_gid,
            "xattrs": {
                name: os.getxattr(path, name, follow_symlinks=False).hex()
                for name in sorted(os.listxattr(path, follow_symlinks=False))
            },
        }
        if stat.S_ISREG(info.st_mode):
            with path.open("rb") as stream:
                item["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        elif path.is_symlink():
            item["target"] = os.readlink(path)
        elif not path.is_dir():
            raise ValueError(f"Unexpected special file in Android partition: {path}")
        entries[str(path.relative_to(root))] = item
    if "security.selinux" not in entries["."]["xattrs"]:
        raise ValueError("Filesystem root lost its SELinux label")
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["record", "check"])
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    actual = snapshot(args.root)
    if args.mode == "record":
        args.manifest.write_text(json.dumps(actual, sort_keys=True))
    else:
        expected = json.loads(args.manifest.read_text())
        differences = [name for name in actual.keys() | expected.keys()
                       if actual.get(name) != expected.get(name)]
        if differences:
            raise SystemExit(f"Filesystem metadata/content mismatch: {differences[:10]}")
        print(f"EROFS verified: {len(actual)} entries, including ownership and SELinux labels")


if __name__ == "__main__":
    main()
