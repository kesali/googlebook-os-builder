#!/usr/bin/env python3
"""Pull the facts we need out of an x86 Linux kernel image (bzImage).

    kernel_info.py <bzImage> <out-dir>

Writes:
    <out-dir>/vmlinux       the uncompressed kernel
    <out-dir>/config        its build configuration (needs CONFIG_IKCONFIG)
    <out-dir>/version.txt   its "Linux version ..." banner

The compressed kernel is found through the boot header fields
payload_offset and payload_length (Linux Documentation/arch/x86/boot.rst).
"""

import gzip
import re
import struct
import subprocess
import sys
from pathlib import Path

LZ4_LEGACY_MAGIC = bytes.fromhex("02214c18")


def compressed_payload(bzimage):
    if bzimage[0x202:0x206] != b"HdrS":
        sys.exit("kernel_info.py: not an x86 bzImage")
    setup_sects = bzimage[0x1F1] or 4  # 0 means 4, for historical reasons
    payload_offset, payload_length = struct.unpack_from("<II", bzimage, 0x248)
    protected_mode_start = (setup_sects + 1) * 512
    start = protected_mode_start + payload_offset
    return bzimage[start : start + payload_length]


def decompress(payload):
    if payload.startswith(LZ4_LEGACY_MAGIC):
        # The kernel build appends the uncompressed size (4 bytes, little endian).
        expected_size = struct.unpack("<I", payload[-4:])[0]
        vmlinux = subprocess.run(
            ["lz4", "-d", "-c"], input=payload[:-4], stdout=subprocess.PIPE, check=True
        ).stdout
        if len(vmlinux) != expected_size:
            sys.exit(f"kernel_info.py: LZ4 gave {len(vmlinux)} bytes, expected {expected_size}")
        return vmlinux
    sys.exit(f"kernel_info.py: unsupported kernel compression (starts with {payload[:4].hex()}); add it here")


def embedded_config(vmlinux):
    """CONFIG_IKCONFIG stores the gzipped .config between two markers."""
    start = vmlinux.find(b"IKCFG_ST")
    end = vmlinux.find(b"IKCFG_ED", start)
    if start < 0 or end < 0:
        sys.exit("kernel_info.py: kernel has no embedded config (CONFIG_IKCONFIG is off)")
    return gzip.decompress(vmlinux[start + len(b"IKCFG_ST") : end])


def version_banner(vmlinux):
    match = re.search(rb"Linux version [ -~]+", vmlinux)
    if not match:
        sys.exit("kernel_info.py: no 'Linux version' banner found")
    return match.group().decode()


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    bzimage = Path(sys.argv[1]).read_bytes()
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    vmlinux = decompress(compressed_payload(bzimage))
    (out / "vmlinux").write_bytes(vmlinux)
    (out / "config").write_bytes(embedded_config(vmlinux))
    (out / "version.txt").write_text(version_banner(vmlinux) + "\n")


if __name__ == "__main__":
    main()
