#!/usr/bin/env python3
"""Expand native-format hardware declarations; never edit Google's files or build outputs."""

import argparse
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
HARDWARE = REPO / "hardware"
DEVICE = HARDWARE / "lenovo-e50-80"
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def drivers():
    names = []
    for line in (DEVICE / "drivers.list").read_text().splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        if not NAME.fullmatch(name) or name in names:
            raise ValueError(f"Invalid or duplicate driver recipe: {name}")
        directory = HARDWARE / "drivers" / name
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"Missing or symlinked driver recipe: {name}")
        names.append(name)
    if not names:
        raise ValueError("Lenovo driver recipe list is empty")
    return names


def expand(path):
    path = Path(path)
    result = []
    text = path.read_text()
    surfaces = {
        REPO / "kernel/gki.config": "gki.config",
        REPO / "kernel/laptop-modules.list": "modules.list",
        REPO / "android/vendor_dlkm/install.list": "install.list",
        REPO / "android/vendor/install.list": "vendor.install",
    }
    fragment = surfaces.get(path.resolve())
    selected = drivers() if fragment or "# recipe:" in text else []
    seen = set()
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("# recipe:") and not line.startswith("# recipe: "):
            raise ValueError(f"Malformed recipe include in {path}: {line.strip()}")
        if not line.startswith("# recipe: "):
            result.append(line)
            continue
        reference = line.removeprefix("# recipe: ").strip()
        parts = reference.split("/")
        if len(parts) != 2 or reference in seen:
            raise ValueError(f"Invalid or duplicate recipe include in {path}: {reference}")
        name, filename = parts
        if name == "lenovo-e50-80" and filename == "vendor.install":
            source = DEVICE / filename
        elif name in selected and filename in ("gki.config", "modules.list", "install.list"):
            source = HARDWARE / "drivers" / name / filename
        else:
            raise ValueError(f"Unknown or unselected recipe in {path}: {reference}")
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Missing or symlinked recipe fragment: {source}")
        text = source.read_text()
        if "# recipe:" in text or not text.endswith("\n"):
            raise ValueError(f"Nested or unterminated recipe fragment: {source}")
        seen.add(reference)
        result.append(text)
    if fragment:
        expected = ({f"lenovo-e50-80/{fragment}"} if fragment == "vendor.install"
                    else {f"{name}/{fragment}" for name in selected})
        if seen != expected:
            raise ValueError(f"{path}: selected recipes must be included exactly once")
    return "".join(result)


def validate():
    for surface in ("kernel/gki.config", "kernel/laptop-modules.list",
                    "android/vendor_dlkm/install.list", "android/vendor/install.list"):
        expand(REPO / surface)
    for name in drivers():
        directory = HARDWARE / "drivers" / name
        modules = set()
        for line in (directory / "modules.list").read_text().splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            if not re.fullmatch(r"(?:drivers|sound)/[A-Za-z0-9_/-]+\.ko", line) or ".." in line:
                raise ValueError(f"Invalid source module in {name}: {line}")
            module = Path(line).name
            if module in modules:
                raise ValueError(f"Duplicate source module in {name}: {module}")
            modules.add(module)
        installed = set()
        for line in (directory / "install.list").read_text().splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 5:
                raise ValueError(f"Invalid install entry in {name}: {line}")
            module = Path(fields[0]).name
            if fields != [f"lib/modules/{module}", "0644", "0:0",
                          "vendor_kernel_modules", f"gki/{module}"] or module in installed:
                raise ValueError(f"Invalid or duplicate module install in {name}: {line}")
            installed.add(module)
        if not modules or modules != installed:
            raise ValueError(f"{name}: source and installed module lists differ")
    modules_patch = (REPO / "android/vendor_dlkm/modules.patch").read_text()
    for module, alias in aliases().items():
        if f"+alias {alias} {module.replace('-', '_')}\n" not in modules_patch:
            raise ValueError(f"Source-derived modules.patch omits recipe alias: {module}")


def aliases():
    result = {}
    for name in drivers():
        source = HARDWARE / "drivers" / name / "aliases"
        if source.is_symlink():
            raise ValueError(f"Symlinked alias recipe: {source}")
        for line in source.read_text().splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 2 or not re.fullmatch(r"[a-z0-9_-]+", fields[0]):
                raise ValueError(f"Invalid recipe alias: {line}")
            module, alias = fields
            if module in result:
                raise ValueError(f"Duplicate recipe alias for {module}")
            result[module] = alias
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        if args.path:
            print(expand(args.path), end="")
        else:
            validate()
            print("Lenovo driver recipes, module installs and metadata aliases agree")
    except (OSError, ValueError) as error:
        parser.exit(1, f"hardware-recipes: {error}\n")


if __name__ == "__main__":
    main()
