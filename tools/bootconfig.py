#!/usr/bin/env python3
"""Read: bootconfig text files (key=value lines). Write: the binary block the kernel
finds at the end of the initrd (Documentation/admin-guide/bootconfig.rst):

    text, NUL-terminated and padded to 4 bytes | u32 size | u32 checksum | "#BOOTCONFIG\\n"

    bootconfig.py <output> <text file>...
"""
import struct
import sys


def lines(path):
    with open(path) as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):
                yield line


def main(output, *inputs):
    text = "".join(f"{line}\n" for path in inputs for line in lines(path)).encode() + b"\0"
    text += b"\0" * (-len(text) % 4)
    checksum = sum(text) & 0xFFFFFFFF
    with open(output, "wb") as file:
        file.write(text + struct.pack("<II", len(text), checksum) + b"#BOOTCONFIG\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
