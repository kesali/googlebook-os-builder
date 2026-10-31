#!/usr/bin/env bash
# Read: one pristine EROFS partition + explicit overlay inputs. Write: a new verified EROFS.
# fakeroot keeps Android's uid/gid, modes and xattrs without a privileged container or mount.
set -euo pipefail
partition=$1 google=$(realpath "$2") emulator=$(realpath -m "$3") mesa=$(realpath -m "$4")
crossystem=$(realpath -m "$5") output=$(realpath -m "$6")
tools=$(cd "$(dirname "$0")/../tools" && pwd)
test -n "${FAKEROOTKEY:-}" || { echo "android-partition.sh requires fakeroot" >&2; exit 1; }
mkdir -p "$(dirname "$output")"
work=$(mktemp -d "$output.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
source=$google/super/${partition}_a.img
fsck.erofs --extract="$work/root" --xattrs --preserve "$source"
python3 "$tools/android_overlay.py" "$partition" "$work/root" "$emulator" "$mesa" "$google" "$crossystem"
python3 "$tools/fs_metadata.py" record "$work/root" "$work/metadata.json"
uuid=$(dump.erofs "$source" | awk '/UUID/ {print $NF}')
test -n "$uuid"
mkfs.erofs -zlz4hc,12 -C262144 -T0 -U "$uuid" "$work/new.img" "$work/root"
fsck.erofs --extract="$work/check" --xattrs --preserve "$work/new.img"
python3 "$tools/fs_metadata.py" check "$work/check" "$work/metadata.json"
if [ "$(stat -c %s "$work/new.img")" -gt "$(stat -c %s "$source")" ]; then
    echo "$partition no longer fits its logical partition; refusing to truncate it." >&2
    exit 1
fi
mv "$work/new.img" "$output"
