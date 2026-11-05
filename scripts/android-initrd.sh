#!/usr/bin/env bash
# Read: Google's boot ramdisks and bootconfig + our bootconfig. Write: the initrd, assembled
# the way a Googlebook's firmware does it (boot image v4):
#
#   platform ramdisk | kernel module ramdisk | generic ramdisk | bootconfig
#
#   android-initrd.sh <google dir> <our bootconfig.txt> <merged module ramdisk> <output>
set -euo pipefail
google=$1 bootconfig=$2 modules=$3 output=$4
tools=$(cd "$(dirname "$0")/../tools" && pwd)
mkdir -p "$(dirname "$output")"
work=$(mktemp -d "$output.XXXXXX")
trap 'rm -rf "$work"' EXIT

# Android looks for its partitions on the disk holding this partition. Our disk keeps
# Google's partition IDs (tools/android_disk.py); the kernel reports them in lower case.
uuid=$(python3 - "$google/gpt.json" <<'EOF'
import json, sys
table = json.load(open(sys.argv[1]))["partitiontable"]
print(next(p["uuid"] for p in table["partitions"] if p.get("name") == "EFI-SYSTEM").lower())
EOF
)
echo "androidboot.boot_part_uuid=$uuid" >"$work/disk.txt"
python3 "$tools/bootconfig.py" "$work/bootconfig" \
    "$google/vendor_boot/bootconfig" "$bootconfig" "$work/disk.txt"

# vendor_ramdisk00 is the platform ramdisk (type 1), 02 the kernel modules (type 3, "dlkm");
# 01 is the recovery ramdisk, which a normal boot doesn't load.
cat "$google/vendor_boot/vendor_ramdisk00" "$modules" \
    "$google/init_boot/ramdisk" "$work/bootconfig" >"$work/initrd"
mv "$work/initrd" "$output"
