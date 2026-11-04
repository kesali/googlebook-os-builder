#!/usr/bin/env python3
"""Expand native-format hardware declarations; never edit Google's files or build outputs."""

import argparse
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
HARDWARE = REPO / "hardware"
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
PARTITIONS = ("system", "vendor", "system_ext", "vendor_dlkm", "module_ramdisk")


def selection(path, root):
    if path.is_symlink() or root.resolve() != root.absolute():
        raise ValueError(f"Symlinked recipe selection: {path}")
    names = []
    for line in path.read_text().splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        if not NAME.fullmatch(name) or name in names:
            raise ValueError(f"Invalid or duplicate recipe in {path}: {name}")
        directory = root / name
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"Missing or symlinked recipe: {name}")
        names.append(name)
    if not names:
        raise ValueError(f"Recipe list is empty: {path}")
    return names


def drivers():
    return selection(HARDWARE / "drivers.list", HARDWARE / "drivers")


def recipes():
    result = {name: HARDWARE / "drivers" / name for name in drivers()}
    for name in selection(HARDWARE / "devices.list", HARDWARE):
        if name in result:
            raise ValueError(f"Device recipe duplicates driver name: {name}")
        result[name] = HARDWARE / name
    return result


def fragment_kind(path):
    surfaces = {
        REPO / "kernel/gki.config": "gki.config",
        REPO / "kernel/laptop-modules.list": "modules.list",
        REPO / "kernel/firmware.list": "firmware.list",
    }
    for partition in PARTITIONS:
        for listing, suffix in (("install.list", "install"), ("remove.list", "remove"),
                                ("patches.list", "patches")):
            surfaces[REPO / "android" / partition / listing] = f"{partition}.{suffix}"
    return surfaces.get(path.resolve())


def fragments(directory, kind):
    path = directory / kind
    result = [path] if path.exists() or path.is_symlink() else []
    if kind.endswith(".patches"):
        result.extend(sorted(directory.glob(kind.replace(".patches", "-*.patches"))))
    return result


def recipe_file(directory, relative):
    path = directory / relative
    if not relative or Path(relative).is_absolute() or any(
        part in ("", ".", "..") for part in relative.split("/")
    ):
        raise ValueError(f"Invalid recipe path: {relative}")
    if path.resolve() != path.absolute() or not path.is_file():
        raise ValueError(f"Missing or symlinked recipe file: {path}")
    return path


def fragment_text(source):
    text = source.read_text()
    if "# recipe:" in text or not text.endswith("\n"):
        raise ValueError(f"Nested or unterminated recipe fragment: {source}")
    result = []
    for line in text.splitlines(keepends=True):
        if line.strip() and not line.startswith("#"):
            if source.name.endswith(".install"):
                fields = line.split()
                if len(fields) != 5:
                    raise ValueError(f"Invalid recipe install entry: {source}: {line.strip()}")
                if fields[4].startswith("./"):
                    local = recipe_file(source.parent, fields[4][2:])
                    fields[4] = "hardware/" + str(local.relative_to(HARDWARE))
                    line = " ".join(fields) + "\n"
            elif source.name.endswith(".patches"):
                local = recipe_file(source.parent, line.strip())
                line = str(local.relative_to(REPO)) + "\n"
        result.append(line)
    return "".join(result)


def expand(path):
    path = Path(path)
    result = []
    text = path.read_text()
    fragment = fragment_kind(path)
    selected = recipes() if fragment or "# recipe:" in text else {}
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
        if name not in selected or not re.fullmatch(r"[a-z0-9_-]+(?:-[a-z0-9]+)*\.[a-z]+", filename):
            raise ValueError(f"Unknown or unselected recipe in {path}: {reference}")
        source = recipe_file(selected[name], filename)
        if fragment and source not in fragments(selected[name], fragment):
            raise ValueError(f"Recipe fragment does not belong to {path}: {reference}")
        seen.add(reference)
        result.append(fragment_text(source))
    if fragment:
        expected = {f"{name}/{source.name}" for name, directory in selected.items()
                    for source in fragments(directory, fragment)}
        if seen != expected:
            raise ValueError(f"{path}: selected recipes must be included exactly once")
    return "".join(result)


def validate():
    for surface in ("kernel/gki.config", "kernel/laptop-modules.list",
                    "kernel/firmware.list"):
        expand(REPO / surface)
    for partition in PARTITIONS:
        directory = REPO / "android" / partition
        for name in ("install.list", "remove.list"):
            if (directory / name).exists():
                expand(directory / name)
        patches(directory)
    for name in drivers():
        directory = HARDWARE / "drivers" / name
        if not (directory / "modules.list").exists():
            if (directory / "vendor_dlkm.install").exists():
                raise ValueError(f"{name}: module installs without a module list")
            continue
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
        for line in (directory / "vendor_dlkm.install").read_text().splitlines():
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
    modules_patch = "".join(path.read_text() for path in patches(REPO / "android/vendor_dlkm"))
    for module, alias in aliases().items():
        if f"+alias {alias} {module.replace('-', '_')}\n" not in modules_patch:
            raise ValueError(f"Source-derived modules.patch omits recipe alias: {module}")


def aliases():
    result = {}
    for name in drivers():
        source = HARDWARE / "drivers" / name / "aliases"
        if source.is_symlink():
            raise ValueError(f"Symlinked alias recipe: {source}")
        if not source.exists():
            continue
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


def patches(changes):
    changes = Path(changes).absolute()
    listing = changes / "patches.list"
    local = set(changes.glob("*.patch"))
    if listing.is_symlink():
        raise ValueError(f"Symlinked patch manifest: {listing}")
    if not listing.exists():
        kind = fragment_kind(listing)
        if kind and any(fragments(directory, kind) for directory in recipes().values()):
            raise ValueError(f"{listing}: selected recipe patches require a patch manifest")
        return [recipe_file(changes, path.name) for path in sorted(local)]
    recipe_file(changes, listing.name)
    result = []
    selected = recipes()
    for line in expand(listing).splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        relative = line.strip()
        if relative.startswith("hardware/"):
            path = REPO / relative
            owners = [directory for directory in selected.values()
                      if path.is_relative_to(directory)]
            if len(owners) != 1:
                raise ValueError(f"Patch is outside selected recipes: {relative}")
            recipe_file(owners[0], str(path.relative_to(owners[0])))
        else:
            path = recipe_file(changes, relative)
        if path.suffix != ".patch" or path in result:
            raise ValueError(f"Invalid or duplicate overlay patch: {relative}")
        result.append(path)
    if local - set(result):
        raise ValueError(f"{listing}: local patches must be included exactly once")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patches", action="store_true")
    parser.add_argument("path", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        if args.patches:
            if not args.path:
                parser.error("--patches needs an Android change directory")
            for path in patches(args.path):
                print(path)
        elif args.path:
            print(expand(args.path), end="")
        else:
            validate()
            print("Hardware recipes, module installs and metadata aliases agree")
    except (OSError, ValueError) as error:
        parser.exit(1, f"hardware-recipes: {error}\n")


if __name__ == "__main__":
    main()
