#!/usr/bin/env python3
"""Verify newly installed laptop modules against their declared dependency metadata."""

import argparse
from pathlib import Path
import subprocess
from hardware_recipes import aliases as recipe_aliases, expand


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


# Verified laptop devices; only these aliases are added for our modules.
LAPTOP_ALIASES = {
    "amdgpu": "pci:v00001002d000015E7sv*sd*bc*sc*i*",
    "mt7921e": "pci:v000014C3d00000616sv*sd*bc*sc*i*",
    "snd-rn-pci-acp3x": "pci:v00001022d000015E2sv*sd*bc04sc80i00*",
    "snd-acp3x-pdm-dma": "platform:acp_rn_pdm_dma",
    "snd-acp3x-rn": "platform:acp_pdm_mach",
    "i915": "pci:v00008086d00001616sv*sd*bc03sc*i*",
}
for module, alias in recipe_aliases().items():
    if module in LAPTOP_ALIASES:
        raise ValueError(f"Recipe duplicates base alias: {module}")
    LAPTOP_ALIASES[module] = alias


def check(root, install_list):
    modules = root / "lib/modules"
    dependencies = {}
    system_modules = set()
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
    installed_aliases = (modules / "modules.alias").read_text().splitlines()
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
