#!/usr/bin/env bash
# Read: verified Google emulator zip + Google's vendor and system images.
# Write: the emulator's vendor and system partition trees + the software Gatekeeper APEX.
# No loop devices/mounts: sfdisk and lp.py find the filesystems and debugfs reads ext4.
#
#   emulator.sh <emulator zip> <Google super directory> <output>
set -euo pipefail
archive=$1 google_super=$2 out=$3
tools=$(cd "$(dirname "$0")/../tools" && pwd)
mkdir -p "$(dirname "$out")"
work=$(mktemp -d "$out.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT

# Prints the start sector and sector count of the named GPT partition in a disk image.
gpt_partition() {
    sfdisk --json "$1" | python3 -c '
import json, sys
table = json.load(sys.stdin)["partitiontable"]
assert table["sectorsize"] == 512
part, = [p for p in table["partitions"] if p.get("name") == sys.argv[1]]
print(part["start"], part["size"])
' "$2"
}

unzip -p "$archive" x86_64/vendor.img > "$work/vendor-disk.img"
read -r start size < <(gpt_partition "$work/vendor-disk.img" vendor)
dd if="$work/vendor-disk.img" of="$work/vendor.ext4" bs=512 skip="$start" count="$size" status=none
mkdir "$work/vendor" "$work/gatekeeper" "$work/system"
debugfs -R "rdump / $work/vendor" "$work/vendor.ext4" > "$work/extract.log" 2>&1
test -s "$work/vendor/bin/hw/android.hardware.security.keymint-service" || {
    cat "$work/extract.log" >&2; exit 1;
}
unzip -p "$work/vendor/apex/com.android.hardware.gatekeeper.nonsecure.apex" apex_payload.img > "$work/gatekeeper.ext4"
debugfs -R "rdump / $work/gatekeeper" "$work/gatekeeper.ext4" >> "$work/extract.log" 2>&1
test -s "$work/gatekeeper/bin/hw/android.hardware.gatekeeper-service.nonsecure" || {
    cat "$work/extract.log" >&2; exit 1;
}
rm "$work/vendor-disk.img" "$work/vendor.ext4" "$work/gatekeeper.ext4"

# The system disk holds a super partition; its system partition is ext4.
unzip -p "$archive" x86_64/system.img > "$work/system-disk.img"
read -r start size < <(gpt_partition "$work/system-disk.img" super)
python3 "$tools/lp.py" extract "$work/system-disk.img" "$work" --offset $((start * 512)) system
rm "$work/system-disk.img"
debugfs -R "rdump / $work/system" "$work/system.img" > "$work/extract.log" 2>&1
test -s "$work/system/system/lib64/libz.so" || {
    cat "$work/extract.log" >&2; exit 1;
}
rm "$work/system.img" "$work/extract.log"

# The donor files must come from the same Android release (API level) as Google's image.
vendor_api() { sed -n 's/^ro\.vendor\.build\.version\.sdk=//p'; }
system_api() { sed -n 's/^ro\.system\.build\.version\.sdk=//p'; }
donor=$(vendor_api < "$work/vendor/build.prop")
target=$(dump.erofs --path=/build.prop --cat "$google_super/vendor_a.img" | vendor_api)
if [ "$donor" != 37 ] || [ "$donor" != "$target" ]; then
    echo "Donor vendor API $donor does not match Google's $target (expected 37)" >&2
    exit 1
fi
donor=$(system_api < "$work/system/system/build.prop")
target=$(dump.erofs --path=/system/build.prop --cat "$google_super/system_a.img" | system_api)
if [ "$donor" != 37 ] || [ "$donor" != "$target" ]; then
    echo "Donor system API $donor does not match Google's $target (expected 37)" >&2
    exit 1
fi
rm -rf "$out"
touch "$work/.ready"
mv "$work" "$out"
