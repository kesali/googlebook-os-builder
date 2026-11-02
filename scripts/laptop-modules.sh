#!/usr/bin/env bash
# Read: built GKI modules, its signing key, an explicit module list, Google's toolchain and
# Google's partitions. Write: stripped, signed laptop modules; never publishes the signing key.
#
#   laptop-modules.sh <kernel build> <toolchain> <module list> <google> <output>
set -euo pipefail
build=$(realpath "$1") toolchain=$(realpath "$2")
list=$(realpath "$3") google=$(realpath "$4") output=$(realpath -m "$5")
mkdir -p "$output"
work=$(mktemp -d "$output.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
hash=$(sed -n 's/^CONFIG_MODULE_SIG_HASH="\([^"]*\)"$/\1/p' "$build/.config")
test -n "$hash" || { echo "No module-signing algorithm in $build/.config" >&2; exit 1; }

while read -r path; do
    [[ -z "$path" || "$path" == \#* ]] && continue
    [[ ( "$path" == drivers/*.ko || "$path" == sound/*.ko ) && "$path" != *..* ]] || {
        echo "Invalid laptop module path: $path" >&2; exit 1;
    }
    name=${path##*/}
    "$toolchain/clang/bin/llvm-strip" --strip-debug -o "$work/$name" "$build/$path"
    # Signed modules can use GKI's protected exports. The corresponding public key is
    # already in this kernel; Google's trusted certificate and ABI list remain unchanged.
    "$build/scripts/sign-file" "$hash" "$build/certs/signing_key.pem" \
        "$build/certs/signing_key.x509" "$work/$name"
    if ! cmp -s "$work/$name" "$output/$name"; then
        mv "$work/$name" "$output/$name"
    fi
    (cd "$output" && sha256sum "$name") >> "$work/manifest"
done < "$list"
test -s "$work/manifest"

# Our modules link against Google's prebuilt helpers (drm, cfg80211, mac80211, ...), whose
# exports are trimmed to what Google's own modules use. depmod checks every symbol and CRC our
# modules import against Google's actual vendor_dlkm and system_dlkm modules plus this kernel.
release=$(cat "$build/include/config/kernel.release")
tree=$work/depmod/lib/modules/$release
mkdir -p "$tree"
fsck.erofs --extract="$tree/vendor" "$google/super/vendor_dlkm_a.img" > /dev/null
fsck.erofs --extract="$tree/system" "$google/super/system_dlkm_a.img" > /dev/null
awk -F'\t' '$3 == "vmlinux"' "$build/Module.symvers" > "$work/vmlinux.symvers"
while read -r _ name; do
    if [ -e "$tree/vendor/lib/modules/$name" ]; then
        echo "$name would replace Google's module" >&2; exit 1
    fi
    cp "$output/$name" "$tree/vendor/lib/modules/$name"
done < "$work/manifest"
depmod -b "$work/depmod" -e -E "$work/vmlinux.symvers" "$release" 2> "$work/depmod.log" || {
    cat "$work/depmod.log" >&2; exit 1;
}
ours=$(awk '{sub(/\.ko$/, "", $2); print $2}' "$work/manifest" | paste -sd'|')
if grep -E "/($ours)\.ko (needs unknown symbol|disagrees about version)" "$work/depmod.log" >&2; then
    echo "Laptop modules do not match Google's helper modules or this kernel" >&2
    exit 1
fi

if ! cmp -s "$work/manifest" "$output/manifest"; then
    mv "$work/manifest" "$output/manifest"
fi
