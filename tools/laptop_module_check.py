#!/usr/bin/env python3
"""Verify newly installed laptop modules against their declared dependency metadata."""

import argparse
from pathlib import Path
import subprocess
from hardware_recipes import aliases as recipe_aliases, expand, recipes


def dependency_closure(direct, dependencies, system_modules=frozenset()):
    """Modules in system_modules come from system_dlkm, which has its own modules.dep."""
    result = set()
    pending = list(direct)
    while pending:
        name = pending.pop()
        if name in result:
            continue
        if name in system_modules and name not in dependencies:
            result.add(name)
            continue
        if name not in dependencies:
            raise ValueError(f"No modules.dep entry for {name}")
        result.add(name)
        pending.extend(dependencies[name])
    return result


# Narrow device aliases retained for the existing laptop recipes.
LAPTOP_ALIASES = recipe_aliases()


def check_module_aliases(path, installed, require_all=False):
    module = subprocess.check_output(["modinfo", "-F", "name", str(path)], text=True).strip()
    compiled = set(subprocess.check_output(
        ["modinfo", "-F", "alias", str(path)], text=True).splitlines())
    declared = {line.split()[1] for line in installed
                if line.startswith("alias ") and line.split()[-1] == module}
    if declared - compiled or (require_all and compiled != declared):
        raise ValueError(f"{path.name}: missing hotplug aliases or aliases not in compiled module")


def check(root, install_list):
    modules = root / "lib/modules"
    dependencies = {}
    system_modules = set()
    installed_aliases = (modules / "modules.alias").read_text().splitlines()
    selected = recipes()
    native_alias_modules = set()
    for name in ("common-network", "common-touchpads"):
        directory = selected.get(name)
        if directory is not None:
            native_alias_modules.update(
                Path(line).name for line in expand(directory / "modules.list").splitlines()
                if line.strip() and not line.startswith("#")
            )
    for line in (modules / "modules.dep").read_text().splitlines():
        name, values = line.split(":", 1)
        dependencies[Path(name).name] = [Path(value).name for value in values.split()]
        system_modules.update(Path(value).name for value in values.split()
                              if value.startswith("/system/lib/modules/"))
    for line in expand(install_list).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        path = root / line.split()[0]
        direct = subprocess.check_output(["modinfo", "-F", "depends", str(path)], text=True).strip()
        direct = [name + ".ko" for name in direct.split(",") if name]
        expected = dependency_closure(direct, dependencies, system_modules)
        actual = set(dependencies.get(path.name, []))
        if path.name not in dependencies or actual != expected:
            raise ValueError(f"{path.name}: modules.dep differs from compiled dependencies: "
                             f"missing {sorted(expected - actual)}, extra {sorted(actual - expected)}")
        signer = subprocess.check_output(["modinfo", "-F", "signer", str(path)], text=True).strip()
        if not signer:
            raise ValueError(f"{path.name} is unsigned")
        check_module_aliases(path, installed_aliases, path.name in native_alias_modules)
    for module, alias in LAPTOP_ALIASES.items():
        aliases = subprocess.check_output(
            ["modinfo", "-F", "alias", str(modules / f"{module}.ko")], text=True).splitlines()
        module_name = subprocess.check_output(
            ["modinfo", "-F", "name", str(modules / f"{module}.ko")], text=True).strip()
        if alias not in aliases or f"alias {alias} {module_name}" not in installed_aliases:
            raise ValueError(f"The kernel or installed aliases do not match the laptop's {module} device")
        if module == "i915":
            expected_alias = f"alias {alias} {module_name}"
            if any(line.split()[-1:] == [module_name] and line != expected_alias
                   for line in installed_aliases):
                raise ValueError("i915 aliases must select only the verified Broadwell GPU")
    print("Laptop module signatures, dependency metadata and device aliases verified")


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
