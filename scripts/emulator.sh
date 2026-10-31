#!/usr/bin/env bash
# Read: verified Google emulator zip + Google's vendor image.
# Write: vendor files + the software Gatekeeper APEX.
# No loop devices/mounts: sfdisk finds the vendor filesystem and debugfs reads ext4.
set -euo pipefail
archive=$1 google_vendor=$2 out=$3
mkdir -p "$(dirname "$out")"
work=$(mktemp -d "$out.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
unzip -p "$archive" x86_64/vendor.img > "$work/vendor-disk.img"
sfdisk --json "$work/vendor-disk.img" > "$work/gpt.json"
read -r start size < <(python3 - "$work/gpt.json" <<'PY'
import json, sys
table = json.load(open(sys.argv[1]))["partitiontable"]
assert table["sectorsize"] == 512
part, = [p for p in table["partitions"] if p.get("name") == "vendor"]
print(part["start"], part["size"])
PY
)
dd if="$work/vendor-disk.img" of="$work/vendor.ext4" bs=512 skip="$start" count="$size" status=none
mkdir "$work/vendor" "$work/gatekeeper"
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
# Software KeyMint and Gatekeeper must come from the vendor API level of Google's image.
api() { sed -n 's/^ro\.vendor\.build\.version\.sdk=//p'; }
donor=$(api < "$work/vendor/build.prop")
target=$(dump.erofs --path=/build.prop --cat "$google_vendor" | api)
if [ "$donor" != 37 ] || [ "$donor" != "$target" ]; then
    echo "Security donor vendor API $donor does not match Google's $target (expected 37)" >&2
    exit 1
fi
rm -rf "$out"
touch "$work/.ready"
mv "$work" "$out"
