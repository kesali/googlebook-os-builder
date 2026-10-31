#!/usr/bin/env bash
# Read: Google's module ramdisk + our matching GKI modules. Write: merged first-stage modules.
set -euo pipefail
google=$(realpath "$1") modules=$(realpath "$2") output=$(realpath -m "$3")
tools=$(cd "$(dirname "$0")/../tools" && pwd)
mkdir -p "$(dirname "$output")"
work=$(mktemp -d "$output.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir "$work/root"
lz4 -dc "$google/vendor_boot/vendor_ramdisk02" | (cd "$work/root" && cpio -idm --quiet --no-preserve-owner)
python3 "$tools/qemu_modules.py" "$modules" "$work/root/lib/modules"
find "$work/root" -exec touch -h -d @0 {} +
(cd "$work/root" && find . -print0 | LC_ALL=C sort -z | cpio --null -o -H newc --owner=0:0 --reproducible) \
    | lz4 -l -12 -q > "$work/modules"
if ! cmp -s "$work/modules" "$output"; then
    mv "$work/modules" "$output"
fi
