#!/usr/bin/env bash
# Read: Mesa, libdrm and Expat source + NDK. Write: Android EGL/GLES software drivers.
# The upstream build systems run every time; only changed installed libraries change the manifest.
set -euo pipefail
mesa=$(realpath "$1") drm=$(realpath "$2") expat=$(realpath "$3")
ndk=$(realpath "$4") out=$(realpath -m "$5")
mkdir -p "$out/pkgconfig"
tc=$ndk/toolchains/llvm/prebuilt/linux-x86_64/bin
key=$(printf '%s\n' "$mesa" "$drm" "$expat" "$ndk" | sha256sum | cut -c1-16)
build=$out/build-$key
sysroot=$build/sysroot
cat > "$out/cross.ini.partial" <<EOF
[binaries]
c = '$tc/x86_64-linux-android35-clang'
cpp = ['$tc/x86_64-linux-android35-clang++', '-fno-exceptions', '-static-libstdc++']
ar = '$tc/llvm-ar'
strip = '$tc/llvm-strip'
pkg-config = ['env', 'PKG_CONFIG_LIBDIR=$sysroot/lib64/pkgconfig', '/usr/bin/pkg-config']
[host_machine]
system = 'android'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'
EOF
if ! cmp -s "$out/cross.ini.partial" "$out/cross.ini"; then
    mv "$out/cross.ini.partial" "$out/cross.ini"
else
    rm "$out/cross.ini.partial"
fi

# Configure only on the first build or after this script or the cross file changed; it takes
# seconds. Ninja reruns Meson or CMake by itself when an upstream build file changes.
settings=$(cat "$0" "$out/cross.ini" | sha256sum | cut -d' ' -f1)
configure=false
if [ "$settings" != "$(cat "$build/settings" 2>/dev/null)" ]; then
    configure=true
fi
setup() {
    if [ -f "$1/build.ninja" ]; then meson setup --reconfigure "$@"; else meson setup "$@"; fi
}

if $configure; then
    setup "$build/drm" "$drm" --cross-file "$out/cross.ini" \
        --prefix=/ --libdir=lib64 --buildtype=release -Ddefault_library=static \
        -Dintel=disabled -Damdgpu=disabled -Dradeon=disabled -Dnouveau=disabled \
        -Dvmwgfx=disabled -Dfreedreno=disabled -Dvc4=disabled -Detnaviv=disabled \
        -Dcairo-tests=disabled -Dman-pages=disabled -Dvalgrind=disabled \
        -Dtests=false -Dudev=false
fi
meson compile -C "$build/drm" -j "${JOBS:-4}"
DESTDIR="$sysroot" meson install -C "$build/drm" --no-rebuild --only-changed

if $configure; then
    cmake -S "$expat" -B "$build/expat" -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE="$ndk/build/cmake/android.toolchain.cmake" \
        -DANDROID_ABI=x86_64 -DANDROID_PLATFORM=android-35 -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/ -DCMAKE_INSTALL_LIBDIR=lib64 -DEXPAT_SHARED_LIBS=OFF \
        -DEXPAT_BUILD_TOOLS=OFF -DEXPAT_BUILD_EXAMPLES=OFF -DEXPAT_BUILD_TESTS=OFF \
        -DEXPAT_BUILD_DOCS=OFF -DCMAKE_POSITION_INDEPENDENT_CODE=ON
fi
cmake --build "$build/expat" --parallel "${JOBS:-4}"
DESTDIR="$sysroot" cmake --install "$build/expat"
sed -i "s|^prefix=.*|prefix=$sysroot|" "$sysroot"/lib64/pkgconfig/*.pc

if $configure; then
    setup "$build/mesa" "$mesa" --cross-file "$out/cross.ini" \
        --prefix=/ --libdir=lib64 --buildtype=release -Db_ndebug=true --wrap-mode=nofallback \
        -Dplatforms=android -Dplatform-sdk-version=35 -Dandroid-stub=true \
        -Dandroid-libbacktrace=disabled -Dgallium-drivers=softpipe -Dvulkan-drivers= \
        -Dllvm=disabled -Dgbm=enabled -Dglx=disabled -Degl=enabled \
        -Dgles1=enabled -Dgles2=enabled -Degl-lib-suffix=_mesa -Dgles-lib-suffix=_mesa \
        -Dvalgrind=disabled -Dlibunwind=disabled -Dzstd=disabled
fi
meson compile -C "$build/mesa" -j "${JOBS:-4}"
DESTDIR="$out/install" meson install -C "$build/mesa" --no-rebuild --only-changed --strip
printf '%s\n' "$settings" > "$build/settings"
for file in libEGL_mesa.so libGLESv1_CM_mesa.so libGLESv2_mesa.so libgallium_dri.so; do
    test -s "$out/install/lib64/$file"
done
(cd "$out/install" && find . -type f -name '*.so*' -print0 | sort -z | xargs -0 sha256sum) > "$out/manifest.partial"
if ! cmp -s "$out/manifest.partial" "$out/manifest"; then
    mv "$out/manifest.partial" "$out/manifest"
else
    rm "$out/manifest.partial"
fi
