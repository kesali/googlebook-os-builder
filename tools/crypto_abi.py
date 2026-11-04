"""Check all original crypto exports, including C++ binding and data-object sizes."""

from pathlib import Path
import subprocess
import sys


def exports(path):
    output = subprocess.run(
        ["readelf", "--dyn-syms", "--wide", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    symbols = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 8 or not fields[0].rstrip(":").isdigit():
            continue
        _, _, size, kind, binding, visibility, section, name = fields[:8]
        if section == "UND" or binding == "LOCAL":
            continue
        # Google's AutoFDO marker is not a callable or data API.
        if name == "__llvm_fs_discriminator__":
            continue
        symbols[name] = (kind, binding, visibility, int(size) if kind == "OBJECT" else None)
    if not symbols:
        raise ValueError(f"{path}: no dynamic exports")
    return symbols


def check(original, replacement):
    expected = exports(original)
    actual = exports(replacement)
    missing = sorted(name for name, signature in expected.items()
                     if actual.get(name) != signature)
    if missing:
        raise ValueError(f"{replacement}: {len(missing)} missing or incompatible exports "
                         f"from {original}:\n" + "\n".join(missing))
    print(f"{original}: all {len(expected)} exports match; "
          f"{len(actual.keys() - expected.keys())} additional exports")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: crypto_abi.py ORIGINAL REPLACEMENT")
    try:
        check(Path(sys.argv[1]), Path(sys.argv[2]))
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
