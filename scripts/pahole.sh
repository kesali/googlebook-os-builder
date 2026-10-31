#!/usr/bin/env bash
# Read: Google's pinned dwarves source + the kernel tree's libbpf. Write: <out>/pahole.
#
#   pahole.sh <dwarves source> <kernel source> <out>
#
# pahole turns the kernel's DWARF debug information into BTF. Google built its
# kernel with pahole 1.31 from this same dwarves commit (CONFIG_PAHOLE_VERSION=131).
set -euo pipefail
dwarves=$(realpath "$1") kernel=$(realpath "$2") out=$(realpath -m "$3")
mkdir -p "$out"
work=$(mktemp -d "$out/work.XXXXXX")
trap 'rm -rf "$work"' EXIT

# libbpf from the kernel source we build; static, so pahole runs on its own.
mkdir -p "$work/libbpf"
make --no-print-directory -C "$kernel/tools/lib/bpf" -j"${JOBS:-4}" \
    OUTPUT="$work/libbpf/" prefix="$work/libbpf-root" install
rm -f "$work"/libbpf-root/lib*/libbpf.so*

PKG_CONFIG_PATH=$(echo "$work"/libbpf-root/lib*/pkgconfig) \
    cmake -S "$dwarves" -B "$work/build" -DCMAKE_BUILD_TYPE=Release \
        -DLIBBPF_EMBEDDED=OFF -DBUILD_SHARED_LIBS=OFF
make --no-print-directory -C "$work/build" -j"${JOBS:-4}" pahole
cp "$work/build/pahole" "$out/pahole.partial"
mv "$out/pahole.partial" "$out/pahole"
"$out/pahole" --version
