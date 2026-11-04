#!/usr/bin/env bash
# Read: HttpEngine's pinned BoringSSL source, NDK and Google's Tethering APEX.
# Write: incremental CPU-portable crypto with exactly the original versioned ABI.
#
#   httpengine-crypto.sh <source> <ndk> <google> <output> <engine-version>
set -euo pipefail
source=$(realpath "$1") ndk=$(realpath "$2") google=$(realpath "$3")
output=$(realpath -m "$4")
version=$5
root=$(cd "$(dirname "$0")/.." && pwd)
key=$(printf '%s\n' "$source" "$ndk" \
    "$(sha256sum "$0" "$root/scripts/httpengine-cxx.h")" | sha256sum | cut -c1-16)
build=$output/build-$key
mkdir -p "$build" "$output"
work=$(mktemp -d "$output.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
toolchain=$ndk/toolchains/llvm/prebuilt/linux-x86_64

dump.erofs --path=/system/apex/com.google.android.tethering.apex --cat \
    "$google/super/system_a.img" > "$work/tethering.apex"
unzip -p "$work/tethering.apex" apex_payload.img > "$work/payload.img"
dump.erofs --path=/lib64/libcrypto_httpengine.so --cat "$work/payload.img" > "$work/original.so"
dump.erofs --path=/lib64/libhttpengine.so --cat "$work/payload.img" > "$work/engine.so"
strings "$work/engine.so" > "$work/engine.strings"
grep -Fx "$version" "$work/engine.strings" > /dev/null || {
    echo "HttpEngine no longer matches $version; verify its Chromium DEPS before changing the pin." >&2
    exit 1
}
python3 "$root/tools/crypto_abi.py" --httpengine-version-script "$work/original.so" \
    > "$work/exports.map"
if ! cmp -s "$work/exports.map" "$build/exports.map"; then
    cp "$work/exports.map" "$build/exports.map"
fi

if [ ! -f "$build/build.ninja" ]; then
    cmake -S "$source" -B "$build" -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE="$ndk/build/cmake/android.toolchain.cmake" \
        -DANDROID_ABI=x86_64 -DANDROID_PLATFORM=android-29 -DANDROID_STL=c++_static \
        -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF \
        -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DOPENSSL_SMALL=ON -DFIPS=OFF \
        -DCMAKE_C_FLAGS="-march=x86-64-v3" \
        -DCMAKE_CXX_FLAGS="-march=x86-64-v3 -include $root/scripts/httpengine-cxx.h -D_LIBCPP_DISABLE_EXTERN_TEMPLATE" \
        -DCMAKE_C_FLAGS_RELEASE="-O2 -DNDEBUG -fvisibility=default" \
        -DCMAKE_CXX_FLAGS_RELEASE="-O2 -DNDEBUG -fvisibility=default"
fi
cmake --build "$build" --parallel "${JOBS:-12}" --target crypto

library=$build/libcrypto_httpengine.so
if [ ! -f "$library" ] || [ "$build/libcrypto.a" -nt "$library" ] \
        || [ "$build/exports.map" -nt "$library" ]; then
    "$toolchain/bin/x86_64-linux-android29-clang++" -march=x86-64-v3 -shared \
        -o "$work/libcrypto_httpengine.so" -Wl,-soname,libcrypto_httpengine.so \
        -Wl,--whole-archive "$build/libcrypto.a" -Wl,--no-whole-archive \
        -static-libstdc++ -Wl,--version-script="$build/exports.map" \
        -Wl,--no-undefined -Wl,--no-undefined-version -Wl,-Bsymbolic -Wl,-z,now \
        -Wl,--build-id=sha1
    "$toolchain/bin/llvm-strip" --strip-unneeded "$work/libcrypto_httpengine.so"
    python3 "$root/tools/crypto_abi.py" --exact "$work/original.so" "$work/libcrypto_httpengine.so"
    mv "$work/libcrypto_httpengine.so" "$library"
else
    python3 "$root/tools/crypto_abi.py" --exact "$work/original.so" "$library"
fi
if ! cmp -s "$library" "$output/libcrypto_httpengine.so"; then
    cp "$library" "$work/publish.so"
    mv "$work/publish.so" "$output/libcrypto_httpengine.so"
fi
(cd "$output" && sha256sum libcrypto_httpengine.so) > "$work/manifest"
if ! cmp -s "$work/manifest" "$output/manifest"; then
    mv "$work/manifest" "$output/manifest"
fi
