#!/usr/bin/env bash
# Read: BusyBox source. Write: a static userspace binary (no host libraries on the USB).
set -euo pipefail
source=$(realpath "$1") build=$(realpath -m "$2")
mkdir -p "$build"
mk=(make --no-print-directory -C "$source" O="$build" -j"${JOBS:-4}")
if [ ! -f "$build/.config" ]; then
    "${mk[@]}" defconfig
    sed -i 's/# CONFIG_STATIC is not set/CONFIG_STATIC=y/' "$build/.config"
    # Obsolete ioctl definitions were removed from newer Linux libc headers.
    sed -i 's/CONFIG_TC=y/# CONFIG_TC is not set/' "$build/.config"
    "${mk[@]}" oldconfig </dev/null
fi
"${mk[@]}" busybox
