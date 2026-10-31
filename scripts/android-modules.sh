#!/usr/bin/env bash
# Read: Google's module ramdisk, its change directory and Google's QEMU driver ramdisk.
# Write: the merged first-stage module ramdisk.
# Usage: android-modules.sh GOOGLE CHANGES VIRT_INITRAMFS OUTPUT (under fakeroot)
set -euo pipefail
google=$(realpath "$1") changes=$2 virt_initramfs=$(realpath "$3") output=$(realpath -m "$4")
scripts=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$(dirname "$output")"
work=$(mktemp -d "$output.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir "$work/root" "$work/virt"
lz4 -dc "$google/vendor_boot/vendor_ramdisk02" | (cd "$work/root" && cpio -idm --quiet --no-preserve-owner)
lz4 -dc "$virt_initramfs" | (cd "$work/virt" && cpio -idm --quiet --no-preserve-owner 'lib/modules/*')
# Google built the QEMU drivers for exactly this kernel release; vermagic must match it.
release=$(sed -nE 's/^Linux version ([^ ]+) .*/\1/p' "$google/kernel/version.txt")
virt=$work/virt/lib/modules/$release
if [ ! -d "$virt" ]; then
    echo "No modules for kernel $release in $virt_initramfs" >&2
    exit 1
fi
bash "$scripts/android-overlay.sh" "$changes" "$work/root" virt="$virt"

# modules.patch spells out each module's dependencies; they must match Google's build.
kernel_deps=$(sed -E 's#[^ :]*/([^/ :]+\.ko)#/lib/modules/\1#g' "$virt/modules.dep")
for path in $(awk '!/^#/ && NF {print $1}' "$changes/install.list"); do
    module=/lib/modules/${path##*/}
    expected=$(awk -F: -v module="$module" '$1 == module' <<< "$kernel_deps")
    if [ -z "$expected" ] || ! grep -qxF "$expected" "$work/root/lib/modules/modules.dep" \
            || ! grep -qxF "${path##*/}" "$work/root/lib/modules/modules.load"; then
        echo "modules.patch must load ${path##*/} with: ${expected:-a module in the QEMU driver ramdisk}" >&2
        exit 1
    fi
done

find "$work/root" -exec touch -h -d @0 {} +
(cd "$work/root" && find . -print0 | LC_ALL=C sort -z | cpio --null -o -H newc --owner=0:0 --reproducible) \
    | lz4 -l -12 -q > "$work/modules"
mv "$work/modules" "$output"
