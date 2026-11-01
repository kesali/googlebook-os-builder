#!/usr/bin/env bash
# Read: built GKI modules, its signing key, an explicit module list and Google's toolchain.
# Write: stripped, signed laptop modules; never publishes the private signing key.
#
#   laptop-modules.sh <kernel build> <toolchain> <module list> <output>
set -euo pipefail
build=$(realpath "$1") toolchain=$(realpath "$2")
list=$(realpath "$3") output=$(realpath -m "$4")
mkdir -p "$output"
work=$(mktemp -d "$output.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
hash=$(sed -n 's/^CONFIG_MODULE_SIG_HASH="\([^"]*\)"$/\1/p' "$build/.config")
test -n "$hash" || { echo "No module-signing algorithm in $build/.config" >&2; exit 1; }

while read -r path; do
    [[ -z "$path" || "$path" == \#* ]] && continue
    [[ "$path" == drivers/*.ko && "$path" != *..* ]] || {
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
if ! cmp -s "$work/manifest" "$output/manifest"; then
    mv "$work/manifest" "$output/manifest"
fi
