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
    if [ ! -e "$path" ]; then
        echo "Missing read-only input mount: $path" >&2
        exit 1
    fi
    mounts+=(--volume "$path:$path:ro")
done

# Interactive commands (e.g. `make shell`) need a terminal.
terminal=()
if [ -t 0 ] && [ -t 1 ]; then
    terminal=(--tty)
fi

# QEMU (`make qemu`) uses the host's hardware virtualization when it is available.
devices=()
if [ -e /dev/kvm ]; then
    devices=(--device /dev/kvm --group-add "$(stat -c %g /dev/kvm)")
fi

ports=()
if [ "${2:-}" = scripts/qemu.sh ]; then
    ports=(--publish "127.0.0.1:${QEMU_VNC_PORT:-5900}:5900")
fi

exec docker run --rm --interactive "${terminal[@]}" "${devices[@]}" "${ports[@]}" \
    --user "$(id -u):$(id -g)" --env HOME=/tmp --env JOBS --env SOURCE_DATE_EPOCH --env QEMU_VNC_PORT \
    "${mounts[@]}" --workdir "$PWD" \
    "$image" "$@"
