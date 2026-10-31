#!/usr/bin/env python3
"""Extend Google's first-stage module directory with the source-built QEMU drivers."""

from pathlib import Path
import shutil
import subprocess
import sys


def main():
    modules, destination = map(Path, sys.argv[1:])
    versions = list((modules / "lib/modules").iterdir())
    if len(versions) != 1:
        raise SystemExit("Expected exactly one GKI module version")
    version = versions[0]
    deps = {}
    for line in (version / "modules.dep").read_text().splitlines():
        name, dependencies = line.split(":", 1)
        deps[name] = dependencies.split()

    added = []
    for name in ("virtio-gpu", "virtio_input", "virtio_net"):
        output = subprocess.check_output([
            "modprobe", "--show-depends", "--dirname", str(modules),
            "--set-version", version.name, name,
        ], text=True)
        for line in output.splitlines():
            words = line.split()
            if words[0] == "builtin":
                continue
            if words[0] != "insmod":
                raise ValueError(f"Unexpected modprobe output: {line}")
            source = Path(words[1])
            target = destination / source.name
            if not target.exists():
                shutil.copyfile(source, target)
                relative = str(source.relative_to(version.resolve()))
                added.append((source.name, [Path(dep).name for dep in deps[relative]]))
    with (destination / "modules.dep").open("a") as depfile, (destination / "modules.load").open("a") as loadfile:
        for name, dependencies in added:
            for dep in dependencies:
                if not (destination / dep).is_file():
                    raise ValueError(f"Missing first-stage dependency: {name} -> {dep}")
            # Android treats a trailing space as an empty dependency.
            depfile.write(f"/lib/modules/{name}:" + "".join(f" /lib/modules/{dep}" for dep in dependencies) + "\n")
            loadfile.write(name + "\n")
    print("Added first-stage modules:", ", ".join(name for name, _ in added))


if __name__ == "__main__":
    main()
