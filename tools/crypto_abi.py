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


def check(original, replacement, exact=False):
    expected = exports(original)
    actual = exports(replacement)
    missing = sorted(name for name, signature in expected.items()
                     if actual.get(name) != signature)
    if missing:
        raise ValueError(f"{replacement}: {len(missing)} missing or incompatible exports "
                         f"from {original}:\n" + "\n".join(missing))
    extra = sorted(actual.keys() - expected.keys())
    if exact and extra:
        raise ValueError(f"{replacement}: unexpected exports:\n" + "\n".join(extra))
    print(f"{original}: all {len(expected)} exports match; "
          f"{len(actual.keys() - expected.keys())} additional exports")


def httpengine_version_script(original):
    symbols = exports(original)
    if any(not name.endswith("@@INTERSECTED_SYMBOLS") for name in symbols):
        raise ValueError(f"{original}: expected only @@INTERSECTED_SYMBOLS exports")
    names = sorted(name.split("@")[0] for name in symbols)
    return ("INTERSECTED_SYMBOLS {\n  global:\n"
            + "".join(f"    {name};\n" for name in names)
            + "  local: *;\n};\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact", action="store_true")
    parser.add_argument("--httpengine-version-script", action="store_true")
    parser.add_argument("original", type=Path)
    parser.add_argument("replacement", nargs="?", type=Path)
    args = parser.parse_args()
    if not args.httpengine_version_script and args.replacement is None:
        parser.error("REPLACEMENT is required unless generating the HttpEngine version script")
    if args.httpengine_version_script and (args.replacement or args.exact):
        parser.error("version script generation takes only ORIGINAL")
    try:
        if args.httpengine_version_script:
            print(httpengine_version_script(args.original), end="")
        else:
            check(args.original, args.replacement, exact=args.exact)
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
