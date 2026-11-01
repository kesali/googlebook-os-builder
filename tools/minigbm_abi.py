#!/usr/bin/env python3
"""Check Google's allocator clients against replacement libraries, without changing the image."""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def symbols(path, defined):
    option = "--defined-only" if defined else "--undefined-only"
    output = subprocess.check_output(
        ["nm", "-D", "--format=posix", option, str(path)], text=True)
    return {line.split()[0].split("@")[0] for line in output.splitlines() if line.strip()}


def missing_symbols(original, replacement, imports):
    return sorted((original & imports) - replacement)


def check(image, libraries):
    if image.is_symlink() or not image.is_file():
        raise ValueError("Allocator checks accept only a regular image, never a device/symlink")
    names = ("libminigbm_gralloc.so", "libgbm.so")
    with tempfile.TemporaryDirectory(prefix="abi-", dir=libraries) as temporary:
        vendor = Path(temporary) / "vendor"
        subprocess.run(["fsck.erofs", f"--extract={vendor}", str(image)], check=True)
        originals = {name: symbols(vendor / "lib64" / name, True) for name in names}
        replacements = {name: symbols(libraries / name, True) for name in names}
        imports = {name: set() for name in names}
        clients = {name: 0 for name in names}
        for directory in ("bin", "lib64"):
            for path in (vendor / directory).rglob("*"):
                if path.is_symlink() or not path.is_file():
                    continue
                with path.open("rb") as stream:
                    if stream.read(4) != b"\x7fELF":
                        continue
                dynamic = subprocess.check_output(["readelf", "-dW", str(path)], text=True)
                needed = set(re.findall(r"\(NEEDED\).*?\[(.*?)\]", dynamic)) & set(names)
                if needed:
                    undefined = symbols(path, False)
                    for name in needed:
                        imports[name].update(undefined)
                        clients[name] += 1
        for name in names:
            if not clients[name]:
                raise ValueError(f"No original clients found for {name}; cannot verify its ABI")
            missing = missing_symbols(originals[name], replacements[name], imports[name])
            if missing:
                raise ValueError(f"{name} lacks symbols used by Google's clients:\n" + "\n".join(missing))
            print(f"{name}: all {len(originals[name] & imports[name])} required exports "
                  f"present for {clients[name]} Google clients")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vendor_image", type=Path)
    parser.add_argument("libraries", type=Path)
    args = parser.parse_args()
    try:
        check(args.vendor_image, args.libraries)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"minigbm ABI: {error}\n")


if __name__ == "__main__":
    main()
