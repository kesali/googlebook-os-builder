#!/usr/bin/env bash
# Read: pinned Mesa source and native LLVM/Clang. Write: shader-generation host tools.
#
#   mesa-clc.sh <mesa source> <output>
set -euo pipefail
source=$(realpath "$1") output=$(realpath -m "$2")
key=$(printf '%s\n' "$source" "$(llvm-config-19 --version)" | sha256sum | cut -c1-16)
build=$output/build-$key
mkdir -p "$build" "$output/bin"
export PATH="/usr/lib/llvm-19/bin:$PATH"
settings=$(sha256sum "$0" | cut -d' ' -f1)
if [ ! -f "$build/settings" ] || [ "$settings" != "$(cat "$build/settings")" ]; then
    options=()
    if [ -f "$build/build.ninja" ]; then options+=(--reconfigure); fi
    CC=clang-19 CXX=clang++-19 meson setup "${options[@]}" "$build" "$source" \
        --buildtype=release --wrap-mode=nofallback \
        -Dgallium-drivers= -Dvulkan-drivers= -Dplatforms= \
        -Dglx=disabled -Degl=disabled -Dgbm=disabled \
        -Dllvm=enabled -Dshared-llvm=enabled -Dmesa-clc=enabled \
        -Dinstall-mesa-clc=true -Dgallium-va=disabled -Dlibunwind=disabled \
        -Dzstd=disabled
    printf '%s\n' "$settings" > "$build/settings"
fi
ninja -C "$build" -j "${JOBS:-12}" \
    src/compiler/clc/mesa_clc src/compiler/spirv/vtn_bindgen2
for name in mesa_clc vtn_bindgen2; do
    case "$name" in
        mesa_clc) source_binary=$build/src/compiler/clc/$name ;;
        vtn_bindgen2) source_binary=$build/src/compiler/spirv/$name ;;
    esac
    test -x "$source_binary"
    if ! cmp -s "$source_binary" "$output/bin/$name"; then
        cp "$source_binary" "$output/bin/$name.partial"
        mv "$output/bin/$name.partial" "$output/bin/$name"
    fi
done
(cd "$output" && sha256sum bin/mesa_clc bin/vtn_bindgen2) > "$build/manifest"
if ! cmp -s "$build/manifest" "$output/manifest"; then
    cp "$build/manifest" "$output/manifest.partial"
    mv "$output/manifest.partial" "$output/manifest"
fi
