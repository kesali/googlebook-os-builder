#!/usr/bin/env python3
"""Verify newly installed laptop modules against their declared dependency metadata."""

import argparse
from pathlib import Path
import subprocess


def dependency_closure(direct, dependencies):
    result = set()
    pending = list(direct)
    while pending:
        name = pending.pop()
        if name in result:
            continue
        if name not in dependencies:
            raise ValueError(f"No modules.dep entry for {name}")
        result.add(name)
        pending.extend(dependencies[name])
    return result


def check(root, install_list):
    modules = root / "lib/modules"
    dependencies = {}
    for line in (modules / "modules.dep").read_text().splitlines():
        name, values = line.split(":", 1)
        dependencies[Path(name).name] = [Path(value).name for value in values.split()]
    for line in install_list.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        path = root / line.split()[0]
        direct = subprocess.check_output(["modinfo", "-F", "depends", str(path)], text=True).strip()
        direct = [name + ".ko" for name in direct.split(",") if name]
        expected = dependency_closure(direct, dependencies)
        actual = set(dependencies.get(path.name, []))
        if path.name not in dependencies or actual != expected:
            raise ValueError(f"{path.name}: modules.dep differs from compiled dependencies: "
                             f"missing {sorted(expected - actual)}, extra {sorted(actual - expected)}")
        signer = subprocess.check_output(["modinfo", "-F", "signer", str(path)], text=True).strip()
        if not signer:
            raise ValueError(f"{path.name} is unsigned")
    aliases = subprocess.check_output(
        ["modinfo", "-F", "alias", str(modules / "amdgpu.ko")], text=True).splitlines()
    laptop = "pci:v00001002d000015E7sv*sd*bc*sc*i*"
    if laptop not in aliases or f"alias {laptop} amdgpu" not in (modules / "modules.alias").read_text().splitlines():
        raise ValueError("The kernel or installed aliases do not match the MSI's AMD GPU")
    print("Laptop module signatures, dependency metadata and GPU alias verified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("install_list", type=Path)
    args = parser.parse_args()
    try:
        check(args.root, args.install_list)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"laptop modules: {error}\n")


if __name__ == "__main__":
    main()
