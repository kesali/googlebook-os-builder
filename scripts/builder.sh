#!/usr/bin/env bash
# Run one command inside the builder container (docker/Dockerfile).
#
#   scripts/builder.sh <command> [args...]
#
# The repository is mounted at the same path it has on the host, so a path
# means the same thing inside and outside the container. Files are created
# as the calling user, not as root.
#
# EXTRA_MOUNTS: space-separated host paths (files or directories) outside the
# repository that the command needs; they are mounted read-only at the same
# path. The Makefile uses this for the recovery image.
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
image=${BUILDER_IMAGE:-gbos-dali-builder}

mounts=(--volume "$repo:$repo")
for path in ${EXTRA_MOUNTS:-}; do
    mounts+=(--volume "$path:$path:ro")
done

# Interactive commands (e.g. `make shell`) need a terminal.
terminal=()
if [ -t 0 ] && [ -t 1 ]; then
    terminal=(--tty)
fi

exec docker run --rm --interactive "${terminal[@]}" \
    --user "$(id -u):$(id -g)" --env HOME=/tmp \
    "${mounts[@]}" --workdir "$PWD" \
    "$image" "$@"
