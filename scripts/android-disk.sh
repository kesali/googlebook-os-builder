#!/usr/bin/env bash
# Read: Google's recovery image. Write: a NEW disk image for QEMU. It is Google's disk,
# every partition at Google's offset with Google's contents, with two changes:
#   - userdata moves to the end of the disk and grows to <userdata GiB>. Google's is 4 GiB,
#     too small for Android 17's first boot. It starts empty; Android formats it.
#   - slot A is marked bootable and successful (see below).
#
#   android-disk.sh <recovery image> <userdata GiB> <output>
#
# The disk holds Android's data (/data), so it is never replaced: delete it to start over.
set -euo pipefail
recovery=$1 userdata_gib=$2 output=$3
if [ -e "$output" ]; then
    echo "$output exists; delete it to start over (this erases Android's data)." >&2
    exit 1
fi
mkdir -p "$(dirname "$output")"
disk=$output.partial
trap 'rm -f "$disk"' EXIT

# Instant on btrfs and XFS, which share the unchanged blocks; a full copy elsewhere.
cp --reflink=auto "$recovery" "$disk"

number() { # partition number of a partition name
    sfdisk --dump "$disk" | sed -n "s|^$disk\([0-9]*\) :.*name=\"$1\".*|\1|p"
}
end=$(sfdisk --dump "$disk" | sed -n 's/.*start= *\([0-9]*\), size= *\([0-9]*\).*/\1 \2/p' |
    awk '{ if ($1 + $2 > end) end = $1 + $2 } END { print end }')
userdata_start=$(((end + 2047) / 2048 * 2048)) # 1 MiB aligned, in 512-byte sectors

truncate -s $((userdata_start * 512 + (userdata_gib << 30) + (1 << 20))) "$disk"
sfdisk --quiet --relocate gpt-bak-std "$disk" # the backup partition table goes to the new end
echo "$userdata_start,+" | sfdisk --quiet --no-reread -N "$(number userdata)" "$disk"

# Android's boot control keeps slot state in GPT attribute bits of vbmeta_a/_b, like
# ChromeOS: 48-51 priority, 52-55 tries left, 56 boot successful. Google's image marks
# slot B; we boot A. Without "successful", every boot is treated as an unfinished update.
sfdisk --quiet --part-attrs "$disk" "$(number vbmeta_a)" "GUID:48,49,50,51,56"
sfdisk --quiet --part-attrs "$disk" "$(number vbmeta_b)" ""

mv "$disk" "$output"
trap - EXIT
sfdisk --dump "$output" >"$output.layout.txt"
echo "Disk ready: $output (partition table: $output.layout.txt)"
