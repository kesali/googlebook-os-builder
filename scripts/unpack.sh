#!/usr/bin/env bash
# Unpack Google's recovery image into plain files the rest of the build reads.
#
#   scripts/unpack.sh <recovery.bin> <out-dir>
#
# Reads : the official Googlebook recovery image (never modified).
# Writes: <out-dir>/
#   gpt.json                       partition table of the recovery image
#   partitions/*.img               boot_a, init_boot_a, vendor_boot_a, vbmeta_a, copied as-is
#   partitions/vbmeta_a.txt        what vbmeta_a says (avbtool info_image)
#   super/*.img                    logical partitions inside "super" (system_a, vendor_a, ...)
#   super/layout.txt               their names, sizes and groups
#   boot/ init_boot/ vendor_boot/  contents of the boot images, plus info.txt for each
#   kernel/                        Google's kernel: vmlinux, config, version.txt
#   props/*.prop                   build.prop of each Android partition
#   SHA256SUMS                     checksums of everything above
#   inventory.txt                  one-page summary; written last, so it marks a finished run
#
# Runs inside the builder container (make unpack). Needs about 9 GB free.
set -euo pipefail

recovery=$1
out=$2
tools=$(cd "$(dirname "$0")/../tools" && pwd)

log() { echo ">> $*"; }

# partition_field <name> <start|size>: where a GPT partition is, in 512-byte sectors.
partition_field() {
    local value
    value=$(jq -r --arg name "$1" --arg field "$2" \
        '.partitiontable.partitions[] | select(.name == $name) | .[$field]' "$out/gpt.json")
    if [ -z "$value" ]; then
        echo "no partition named $1 in $recovery" >&2
        exit 1
    fi
    echo "$value"
}

# copy_partition <name> <file>: copy one GPT partition out of the recovery image.
copy_partition() {
    local start size
    start=$(partition_field "$1" start)
    size=$(partition_field "$1" size)
    dd if="$recovery" of="$2" bs=512 skip="$start" count="$size" status=none
}

# prop <key>: value of an Android property, from the first build.prop that sets it.
prop() {
    awk -F= -v key="$1" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "$out"/props/*.prop
}

write_inventory() {
    echo "Googlebook OS recovery image: inventory"
    echo "======================================="
    echo "Input   : $recovery"
    echo "SHA-256 : $recovery_sha256"
    echo
    echo "Android"
    echo "  build       : $(prop ro.system.build.fingerprint)"
    echo "  version     : Android $(prop ro.system.build.version.release), SDK $(prop ro.system.build.version.sdk)"
    echo "  patch level : $(prop ro.build.version.security_patch)"
    echo "  made for    : $(prop ro.product.vendor.model) ($(prop ro.product.vendor.device))"
    echo
    echo "Kernel (config in kernel/config)"
    echo "  $(cat "$out/kernel/version.txt")"
    echo
    echo "Kernel command line from vendor_boot"
    echo "  $(grep -m1 '^vendor command line args:' "$out/vendor_boot/info.txt" | cut -d: -f2-)"
    echo
    echo "Logical partitions in super"
    sed 's/^/  /' "$out/super/layout.txt"
    echo
    echo "Verified boot (vbmeta_a)"
    grep -E '^(Algorithm|Rollback Index|Flags|Release String):' "$out/partitions/vbmeta_a.txt" | sed 's/^/  /'
}

rm -rf "$out"
mkdir -p "$out"/{partitions,super,boot,init_boot,vendor_boot,kernel,props}

log "Partition table"
sfdisk --json "$recovery" > "$out/gpt.json"

log "Boot partitions"
for name in boot_a init_boot_a vendor_boot_a vbmeta_a; do
    copy_partition "$name" "$out/partitions/$name.img"
done

log "Logical partitions inside super (about 8 GB)"
super_start=$(partition_field super start)
super_offset=$((super_start * 512))
python3 "$tools/lp.py" list "$recovery" --offset "$super_offset" > "$out/super/layout.txt"
python3 "$tools/lp.py" extract "$recovery" "$out/super" --offset "$super_offset"

log "Boot image contents"
for name in boot init_boot vendor_boot; do
    unpack_bootimg --boot_img "$out/partitions/${name}_a.img" --out "$out/$name" > "$out/$name/info.txt"
done

log "Kernel version and config"
python3 "$tools/kernel_info.py" "$out/boot/kernel" "$out/kernel"

log "Verified boot data"
avbtool info_image --image "$out/partitions/vbmeta_a.img" > "$out/partitions/vbmeta_a.txt"

log "Android build properties"
# partition image   where its build.prop is inside it
while read -r image path; do
    dump.erofs --path="$path" --cat "$out/super/$image.img" > "$out/props/${image%_a}.prop"
done <<'EOF'
system_a        /system/build.prop
system_ext_a    /etc/build.prop
product_a       /etc/build.prop
vendor_a        /build.prop
vendor_dlkm_a   /etc/build.prop
system_dlkm_a   /etc/build.prop
EOF

log "Checksums (input image is about 19 GB, this takes a minute)"
recovery_sha256=$(sha256sum < "$recovery" | cut -d' ' -f1)
(cd "$out" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum) > "$out/SHA256SUMS"

write_inventory > "$out/inventory.txt.partial"
mv "$out/inventory.txt.partial" "$out/inventory.txt"
log "Done: $out/inventory.txt"
