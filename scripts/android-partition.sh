#!/usr/bin/env bash
# Read: one pristine Google EROFS partition + its change directory. Write: a new verified EROFS.
# fakeroot keeps Android's uid/gid, modes and xattrs without a privileged container or mount.
# Usage: android-partition.sh GOOGLE PARTITION CHANGES OUTPUT [NAME=DIR ...]
# The NAME=DIR inputs are passed to android-overlay.sh for install.list sources.
set -euo pipefail
google=$(realpath "$1") partition=$2 changes=$3 output=$(realpath -m "$4")
shift 4
scripts=$(cd "$(dirname "$0")" && pwd)
tools=$(cd "$scripts/../tools" && pwd)
test -n "${FAKEROOTKEY:-}" || { echo "android-partition.sh requires fakeroot" >&2; exit 1; }
mkdir -p "$(dirname "$output")"
work=$(mktemp -d "$output.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
source=$google/super/${partition}_a.img
fsck.erofs --extract="$work/root" --xattrs --preserve "$source"
bash "$scripts/android-overlay.sh" "$changes" "$work/root" "$@"
if [ "$partition" = vendor ]; then
    dump.erofs --path=/system/etc/llndk.libraries.txt --cat "$google/super/system_a.img" > "$work/llndk.txt"
    bash "$scripts/check-vendor-libs.sh" "$changes/install.list" "$work/root" "$work/llndk.txt"
fi
python3 "$tools/fs_metadata.py" record "$work/root" "$work/metadata.json"
uuid=$(dump.erofs "$source" | awk '/UUID/ {print $NF}')
test -n "$uuid"
# LZ4 like Google's image, at its strongest (HC level 12, 256 KiB clusters) so it still fits the
# partition. Timestamps 0 and Google's UUID make the same input give the same bytes.
mkfs.erofs -zlz4hc,12 -C262144 -T0 -U "$uuid" "$work/new.img" "$work/root"
# Read the new image back: every file, owner, mode and SELinux label must be what we built.
fsck.erofs --extract="$work/check" --xattrs --preserve "$work/new.img"
python3 "$tools/fs_metadata.py" check "$work/check" "$work/metadata.json"
if [ "$(stat -c %s "$work/new.img")" -gt "$(stat -c %s "$source")" ]; then
    echo "$partition no longer fits its logical partition; refusing to truncate it." >&2
    exit 1
fi
mv "$work/new.img" "$output"
