---
description: "Use when writing or editing build shell scripts in scripts/: header comment, arguments, atomic outputs, no root or mounts."
applyTo: "scripts/**/*.sh"
---
# Build scripts

- Start every script with what it reads and writes, then its usage, then strict mode:
  ```bash
  #!/usr/bin/env bash
  # Read: <inputs>. Write: <outputs>.
  #
  #   name.sh <input> <output>
  set -euo pipefail
  source=$(realpath "$1") output=$(realpath -m "$2")
  ```
- Paths and inputs are positional arguments; the [Makefile](../../Makefile) passes every one.
  Environment variables are only the shared settings the Makefile exports (`JOBS`,
  `QEMU_VNC_PORT`, builder settings); no other hidden defaults.
- Scripts run inside the builder container; the repository has the same path inside and outside.
- Build into a temporary sibling (`work=$(mktemp -d "$output.partial.XXXXXX")` with
  `trap 'rm -rf "$work"' EXIT`) and move into place only after all checks pass.
- Replace an output only if its bytes changed (`cmp -s new old || mv`), so make doesn't rebuild
  everything downstream.
- No root, sudo, loop devices, mounts or privileged containers: use fakeroot, debugfs, sfdisk,
  `fsck.erofs`/`mkfs.erofs`.
- Downloads only through [scripts/fetch.sh](../../scripts/fetch.sh) or
  [scripts/git-fetch.sh](../../scripts/git-fetch.sh), with the pin in [sources.mk](../../sources.mk).
- Fail with a clear message when an assumption breaks (`test … || { echo "why" >&2; exit 1; }`).
- Comment *why* (upstream quirk, what Android expects), not what the command does.
