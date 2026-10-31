#!/usr/bin/env bash
# Read: Google's recovery image. Write: a NEW disk image: QEMU's disk, and the layout the
# laptop's USB gets. It is Google's disk, every partition at Google's offset with Google's
# contents, with three changes:
#   - EFI-SYSTEM grows from 64 to 576 MiB over the empty KERN-A beside it and becomes an empty
#     FAT32 filesystem for the boot files. It keeps its partition ID: Android finds its disk
#     through it (android-initrd.sh).
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

# The boot files (GRUB, kernel, initrd, menu) need room for two builds. Google's EFI-SYSTEM is
# empty, and so is KERN-A, which Android never uses and which follows it. Check that before
# changing anything, so a newer Google image that differs is never overwritten.
extent() { # "<start> <size>" of a partition, in 512-byte sectors
    sfdisk --dump "$disk" | sed -n "s|.*start= *\([0-9]*\), size= *\([0-9]*\).*name=\"$1\".*|\1 \2|p"
}
read -r esp_start esp_sectors <<<"$(extent EFI-SYSTEM)"
read -r kern_start kern_sectors <<<"$(extent KERN-A)"
boot_bytes=$(((esp_sectors + kern_sectors) * 512))
if [ "$((esp_start + esp_sectors))" != "$kern_start" ] ||
    ! cmp --silent --bytes="$boot_bytes" --ignore-initial="$((esp_start * 512)):0" "$disk" /dev/zero; then
    echo "EFI-SYSTEM and KERN-A are not adjacent and empty in $recovery; refusing to format them." >&2
    exit 1
fi
sfdisk --quiet --no-reread --delete "$disk" "$(number KERN-A)"
esp_sectors=$((esp_sectors + kern_sectors))
echo "$esp_start,$esp_sectors" | sfdisk --quiet --no-reread -N "$(number EFI-SYSTEM)" "$disk"
# mkfs.vfat sizes clusters for the whole disk file, not this partition: a disk this big would get
# 16 KiB clusters, too few for FAT32, and firmware tells FAT12/16/32 apart by cluster count.
mkfs.vfat -F 32 -s 8 -n DALI-BOOT --offset "$esp_start" "$disk" $((esp_sectors / 2))

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
