#!/usr/bin/env bash
# Read: Google's module ramdisk, its change directory and our GKI modules.
# Write: the merged first-stage module ramdisk.
# Usage: android-modules.sh GOOGLE CHANGES GKI_MODULES OUTPUT (under fakeroot)
set -euo pipefail
google=$(realpath "$1") changes=$2 modules=$(realpath "$3") output=$(realpath -m "$4")
scripts=$(cd "$(dirname "$0")" && pwd)
versions=("$modules"/lib/modules/*)
if [ ${#versions[@]} != 1 ] || [ ! -d "${versions[0]}" ]; then
    echo "Expected exactly one GKI module version in $modules" >&2
    exit 1
fi
gki=${versions[0]}
mkdir -p "$(dirname "$output")"
work=$(mktemp -d "$output.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir "$work/root"
lz4 -dc "$google/vendor_boot/vendor_ramdisk02" | (cd "$work/root" && cpio -idm --quiet --no-preserve-owner)
bash "$scripts/android-overlay.sh" "$changes" "$work/root" gki="$gki"

# modules.patch spells out each module's dependencies; they must match our kernel build.
kernel_deps=$(sed -E 's#[^ :]*/([^/ :]+\.ko)#/lib/modules/\1#g' "$gki/modules.dep")
for path in $(awk '!/^#/ && NF {print $1}' "$changes/install.list"); do
    module=/lib/modules/${path##*/}
    expected=$(awk -F: -v module="$module" '$1 == module' <<< "$kernel_deps")
    if [ -z "$expected" ] || ! grep -qxF "$expected" "$work/root/lib/modules/modules.dep" \
            || ! grep -qxF "${path##*/}" "$work/root/lib/modules/modules.load"; then
        echo "modules.patch must load ${path##*/} with: ${expected:-a module from our GKI}" >&2
        exit 1
    fi
done

find "$work/root" -exec touch -h -d @0 {} +
(cd "$work/root" && find . -print0 | LC_ALL=C sort -z | cpio --null -o -H newc --owner=0:0 --reproducible) \
    | lz4 -l -12 -q > "$work/modules"
mv "$work/modules" "$output"
