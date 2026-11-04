#!/usr/bin/env bash
# Read: upstream BoringSSL, NDK, host Go and Google's pristine libraries.
# Write: incremental Android shared libraries, published only after full export checks.
#
#   boringssl.sh <source> <ndk> <go> <google> <output>
set -euo pipefail
source=$(realpath "$1") ndk=$(realpath "$2") go=$(realpath "$3")
google=$(realpath "$4") output=$(realpath -m "$5")
root=$(cd "$(dirname "$0")/.." && pwd)
key=$(printf '%s\n' "$source" "$ndk" "$go" \
    "$(sha256sum "$0" "$root/scripts/boringssl-platform-cxx.h")" | sha256sum | cut -c1-16)
build=$output/build-$key
mkdir -p "$build/link" "$output"
work=$(mktemp -d "$output.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT

# As in minigbm, use Google's platform libc++ instead of a custom C++ compatibility shim.
dump.erofs --path=/system/lib64/libc++.so --cat "$google/super/system_a.img" > "$work/libc++.so"
if ! cmp -s "$work/libc++.so" "$build/link/libc++.so"; then
    cp "$work/libc++.so" "$build/link/libc++.so"
fi
export GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off
export GOCACHE=$output/go-cache GOPATH=$output/go-path
export GOWORK=$build/go.work
# Upstream runs its hash injector from the build directory; point Go at the source module
# without putting build products inside the editable source tree.
if [ ! -f "$GOWORK" ]; then
    (cd "$build" && "$go/bin/go" work init "$source")
fi
toolchain=$ndk/toolchains/llvm/prebuilt/linux-x86_64
if [ ! -f "$build/build.ninja" ]; then
    cmake -S "$source" -B "$build" -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE="$ndk/build/cmake/android.toolchain.cmake" \
        -DANDROID_ABI=x86_64 -DANDROID_PLATFORM=android-29 -DANDROID_STL=none \
        -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=OFF \
        -DFIPS=ON -DOPENSSL_SMALL=ON -DGO_EXECUTABLE="$go/bin/go" \
        -DCMAKE_C_FLAGS="-march=x86-64-v3 -DBORINGSSL_ANDROID_SYSTEM" \
        -DCMAKE_CXX_FLAGS="-march=x86-64-v3 -DBORINGSSL_ANDROID_SYSTEM -isystem $toolchain/sysroot/usr/include/c++/v1 -include $root/scripts/boringssl-platform-cxx.h" \
        -DCMAKE_CXX_STANDARD_LIBRARIES="$build/link/libc++.so" \
        -DCMAKE_SHARED_LINKER_FLAGS="-Wl,-Bsymbolic"
fi
cmake --build "$build" --parallel "${JOBS:-12}" --target crypto ssl
for library in crypto ssl; do
    "$toolchain/bin/llvm-strip" --strip-unneeded \
        -o "$work/lib$library.so" "$build/lib$library.so"
    for partition in system vendor; do
        prefix=
        if [ "$partition" = system ]; then prefix=system/; fi
        original=$work/$partition-lib$library.so
        dump.erofs --path="/${prefix}lib64/lib$library.so" --cat \
            "$google/super/${partition}_a.img" > "$original"
        python3 "$root/tools/crypto_abi.py" "$original" "$work/lib$library.so"
    done
done
# Conscrypt is the hot loop25 copy in the Lenovo capture. Check the actual APEX libraries,
# not just system/vendor: matching filenames do not guarantee a matching ABI.
dump.erofs --path=/system/apex/com.google.android.conscrypt.apex --cat \
    "$google/super/system_a.img" > "$work/conscrypt.apex"
unzip -p "$work/conscrypt.apex" apex_payload.img > "$work/conscrypt.img"
for library in crypto ssl; do
    dump.erofs --path="/lib64/lib$library.so" --cat "$work/conscrypt.img" \
        > "$work/conscrypt-lib$library.so"
    python3 "$root/tools/crypto_abi.py" "$work/conscrypt-lib$library.so" "$work/lib$library.so"
done
readelf --dyn-syms --wide "$work/libcrypto.so" > "$work/exports"
grep -q ' BORINGSSL_integrity_test$' "$work/exports" || {
    echo "libcrypto.so: missing upstream FIPS integrity self-test" >&2
    exit 1
}
for library in crypto ssl; do
    if ! cmp -s "$work/lib$library.so" "$output/lib$library.so"; then
        mv "$work/lib$library.so" "$output/lib$library.so"
    fi
done
(cd "$output" && sha256sum libcrypto.so libssl.so) > "$work/manifest"
if ! cmp -s "$work/manifest" "$output/manifest"; then
    mv "$work/manifest" "$output/manifest"
fi
