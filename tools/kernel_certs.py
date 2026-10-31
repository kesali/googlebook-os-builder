#!/usr/bin/env python3
"""Copy the X.509 certificates built into a kernel into one PEM file.

    kernel_certs.py <vmlinux> <certs.pem>

Google signs the GKI modules (ramdisks, system_dlkm) with a key made for each
build and then thrown away; only its certificate survives, inside Google's
kernel. Our kernel trusts the same certificate (SYSTEM_TRUSTED_KEYS in
kernel/gki.config). Without it, Google's modules count as unsigned and may not
use "protected" GKI symbols: zram, for one, then fails to load.

A DER certificate starts with two SEQUENCE headers, 30 82 <length> 30 82.
openssl decides which of those byte patterns really are certificates.
"""

import re
import subprocess
import sys
from pathlib import Path

CANDIDATE = re.compile(rb"\x30\x82(..)\x30\x82", re.DOTALL)
MAX_CERTIFICATE = 4096


def certificates(kernel):
    """Yield (subject, PEM text) for every certificate in the kernel image."""
    seen = set()
    for match in CANDIDATE.finditer(kernel):
        length = 4 + int.from_bytes(match[1], "big")
        if length > MAX_CERTIFICATE:
            continue
        der = kernel[match.start() : match.start() + length]
        result = subprocess.run(
            ["openssl", "x509", "-inform", "DER", "-outform", "PEM", "-subject"],
            input=der,
            capture_output=True,
        )
        if result.returncode != 0 or der in seen:
            continue
        seen.add(der)
        subject, pem = result.stdout.decode().split("\n", 1)
        yield subject, pem


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    kernel = Path(sys.argv[1]).read_bytes()
    found = list(certificates(kernel))
    if not found:
        sys.exit("kernel_certs.py: no certificate found; was the kernel built with module signing?")
    for subject, _ in found:
        print(f"kernel certificate: {subject}")
    Path(sys.argv[2]).write_text("".join(pem for _, pem in found))


if __name__ == "__main__":
    main()
