#!/usr/bin/env bash
# Read: pinned AOSP core/extras source and Debian host libraries. Write: native lpmake.
#
#   lpmake.sh <core> <extras> <output>
set -euo pipefail
core=$(realpath "$1") extras=$(realpath "$2") output=$(realpath -m "$3")
root=$(cd "$(dirname "$0")/.." && pwd)
key=$(printf '%s\n' "$core" "$extras" | sha256sum | cut -c1-16)
build=$output/build-$key
settings=$(cat "$0" "$root/tools/lpmake/CMakeLists.txt" | sha256sum | cut -d' ' -f1)
if [ ! -f "$build/settings" ] || [ "$settings" != "$(cat "$build/settings")" ]; then
    cmake -S "$root/tools/lpmake" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DLP_CORE="$core" -DLP_EXTRAS="$extras"
    printf '%s\n' "$settings" > "$build/settings"
fi
cmake --build "$build" --parallel "${JOBS:-12}"
if ! cmp -s "$build/lpmake" "$output/lpmake"; then
    cp "$build/lpmake" "$output/lpmake.partial"
    mv "$output/lpmake.partial" "$output/lpmake"
fi
