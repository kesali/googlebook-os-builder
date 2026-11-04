#!/usr/bin/env bash
# Read: the boot bundle. Write: the boot files (GRUB, kernel, initrd, menu) in the disk image's
# EFI-SYSTEM partition, and nothing else on the disk. The laptop boots from these files once the
# disk image is on the USB.
#
#   android-boot.sh <disk image> <boot bundle directory>
#
# The files are replaced as a whole, so the partition never collects old kernels, and a
# partition that already holds them is not written at all. Rerunning repairs an interrupted run.
set -euo pipefail
disk=$1 bundle=$(realpath "$2")
tools=$(cd "$(dirname "$0")/../tools" && pwd)
test -f "$disk" || { echo "$disk is not a disk image file; this never writes devices." >&2; exit 1; }

# The lock the QEMU runner and android_sync.py hold.
exec 9>"$disk.lock"
flock -n 9 || { echo "The Android disk is already in use." >&2; exit 1; }

# mtools reach a partition of a disk image by its byte offset: no root, mount or loop device.
esp_start=$(sfdisk --dump "$disk" | sed -n 's|.*start= *\([0-9]*\), size=.*name="EFI-SYSTEM".*|\1|p')
test -n "$esp_start" || { echo "$disk has no EFI-SYSTEM partition." >&2; exit 1; }
esp=$disk@@$((esp_start * 512))

# android-disk.sh made this file system; never write into one that is not its work.
label=$(mlabel -s -i "$esp" :: 2>/dev/null || true)
grep -qxE ' *Volume label is GBOS-BOOT *' <<<"$label" ||
    { echo "EFI-SYSTEM in $disk is not the GBOS-BOOT file system; refusing to write it." >&2; exit 1; }

work=$(mktemp -d "$disk.boot.XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir "$work/new"
python3 "$tools/deploy.py" stage "$bundle" "$work/new" >/dev/null

esp_matches_new() { # the partition holds exactly the new files
    rm -rf "$work/current"
    mkdir "$work/current"
    mcopy -s -n -i "$esp" ::EFI ::gbos-builder "$work/current" || return 1
    diff -r "$work/new" "$work/current"
}

if esp_matches_new >/dev/null 2>&1; then
    echo "Boot files in $disk are up to date; nothing written."
    exit 0
fi

for tree in EFI gbos-builder; do
    if mdir -b -i "$esp" "::$tree" >/dev/null 2>&1; then
        mdeltree -i "$esp" "::$tree"
    fi
done
mcopy -s -i "$esp" "$work/new/EFI" "$work/new/gbos-builder" ::
esp_matches_new || { echo "The boot files read back differently from what was written." >&2; exit 1; }
echo "Boot files written to $disk."
