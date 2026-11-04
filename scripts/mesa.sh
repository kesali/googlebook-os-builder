#!/usr/bin/env bash
# Read: Mesa/libdrm/Expat/libva source, NDK and native shader tools. Write: Android GPU libraries.
# The upstream build systems run every time; only changed installed libraries change the manifest.
#
#   mesa.sh <mesa> <libdrm> <expat> <ndk> <output> <libva> <shader tools>
set -euo pipefail
mesa=$(realpath "$1") drm=$(realpath "$2") expat=$(realpath "$3")
ndk=$(realpath "$4") out=$(realpath -m "$5")
libva=$(realpath "$6")
shader_tools=$(realpath "$7")
for name in mesa_clc vtn_bindgen2; do
    test -x "$shader_tools/bin/$name" || {
        echo "Missing native Mesa shader tool: $shader_tools/bin/$name" >&2; exit 1;
    }
done
export PATH="$shader_tools/bin:$PATH"
mkdir -p "$out/pkgconfig"
tc=$ndk/toolchains/llvm/prebuilt/linux-x86_64/bin
key=$(printf '%s\n' "$mesa" "$drm" "$expat" "$ndk" "$libva" | sha256sum | cut -c1-16)
build=$out/build-$key
sysroot=$build/sysroot
va_sysroot=$build/va-sysroot
if [ ! -L "$out/sysroot" ] || [ "$(readlink "$out/sysroot")" != "$sysroot" ]; then
    ln -sfn "$sysroot" "$out/sysroot"
fi
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
mkdir -p "$build"
sed "s|PKG_CONFIG_LIBDIR=$sysroot/lib64/pkgconfig|PKG_CONFIG_LIBDIR=$va_sysroot/lib64/pkgconfig:$sysroot/lib64/pkgconfig|" \
    "$out/cross.ini" > "$build/va-cross.ini.partial"
if ! cmp -s "$build/va-cross.ini.partial" "$build/va-cross.ini"; then
    mv "$build/va-cross.ini.partial" "$build/va-cross.ini"
else
    rm "$build/va-cross.ini.partial"
fi
# Meson caches machine-file binaries; a changed dependency search path needs its
# own build directory rather than reusing the former static-link configuration.
va_build=$build/va-$(sha256sum "$build/va-cross.ini" | cut -c1-16)

# Configure only on the first build or after this script or the cross file changed; it takes
# seconds. Ninja reruns Meson or CMake by itself when an upstream build file changes.
settings=$(cat "$0" "$out/cross.ini" "$shader_tools/manifest" | sha256sum | cut -d' ' -f1)
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
        -Dintel=disabled -Damdgpu=enabled -Dradeon=disabled -Dnouveau=disabled \
        -Dvmwgfx=disabled -Dfreedreno=disabled -Dvc4=disabled -Detnaviv=disabled \
        -Dcairo-tests=disabled -Dman-pages=disabled -Dvalgrind=disabled \
        -Dtests=false -Dudev=false
fi
meson compile -C "$build/drm" -j "${JOBS:-4}"
DESTDIR="$sysroot" meson install -C "$build/drm" --no-rebuild --only-changed

# Only the VA build uses shared DRM helpers. Ship the AMD helper, not the core:
# its libdrm.so dependency is satisfied by Google's unchanged vendor library.
if $configure; then
    setup "$build/drm-va" "$drm" --cross-file "$out/cross.ini" \
        --prefix=/ --libdir=lib64 --buildtype=release -Ddefault_library=shared \
        -Dintel=disabled -Damdgpu=enabled -Dradeon=disabled -Dnouveau=disabled \
        -Dvmwgfx=disabled -Dfreedreno=disabled -Dvc4=disabled -Detnaviv=disabled \
        -Dcairo-tests=disabled -Dman-pages=disabled -Dvalgrind=disabled \
        -Dtests=false -Dudev=false
fi
meson compile -C "$build/drm-va" -j "${JOBS:-4}"
DESTDIR="$va_sysroot" meson install -C "$build/drm-va" --no-rebuild --only-changed
sed -i "s|^prefix=.*|prefix=$va_sysroot|" "$va_sysroot"/lib64/pkgconfig/*.pc

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

# The VA driver uses only libva's headers. Let upstream Meson generate the version
# header, but never compile or install a replacement for Google's libva runtime.
if $configure; then
    setup "$build/libva" "$libva" --cross-file "$out/cross.ini" \
        --prefix=/ --libdir=lib64 --wrap-mode=nofallback \
        -Dwith_x11=no -Dwith_glx=no -Dwith_wayland=no -Dwith_win32=no -Denable_docs=false
    mkdir -p "$sysroot/include/va"
    cp "$libva"/va/*.h "$sysroot/include/va/"
    cp "$build/libva/va/va_version.h" "$sysroot/include/va/"
    cat > "$sysroot/lib64/pkgconfig/libva.pc" <<EOF
prefix=$sysroot
includedir=\${prefix}/include
Name: libva
Description: VA-API development headers only; Google's runtime is preserved
Version: 1.22.0
Cflags: -I\${includedir}
EOF
fi

if $configure; then
    # Google's camera effects require Vulkan 1.2+; strict mode caps RADV and Broadwell's
    # hasvk at 1.1. hasvk is only for Broadwell's camera; Iris GL still renders the screen.
    setup "$build/mesa" "$mesa" --cross-file "$out/cross.ini" \
        --prefix=/ --libdir=lib64 --buildtype=release -Db_ndebug=true --wrap-mode=nofallback \
        -Dplatforms=android -Dplatform-sdk-version=35 -Dandroid-stub=true \
        -Dandroid-libbacktrace=disabled -Dgallium-drivers=softpipe,zink,iris -Dvulkan-drivers=amd,intel_hasvk \
        -Dgallium-va=disabled -Dandroid-strict=false \
        -Dllvm=disabled -Damd-use-llvm=false -Dgbm=enabled -Dgbm-backends-path=/vendor/lib64/gbm \
        -Dglx=disabled -Degl=enabled \
        -Dgles1=enabled -Dgles2=enabled -Degl-lib-suffix=_mesa -Dgles-lib-suffix=_mesa \
        -Dvalgrind=disabled -Dlibunwind=disabled -Dzstd=disabled -Dmesa-clc=system
    # Decode-only RadeonSI needs neither shader compilation nor libelf. Keep its
    # libraries separate from the verified rendering build and Google's loader.
    setup "$va_build" "$mesa" --cross-file "$build/va-cross.ini" \
        --prefix=/ --libdir=lib64 --buildtype=release -Db_ndebug=true --wrap-mode=nofallback \
        -Dplatforms=android -Dplatform-sdk-version=35 -Dandroid-stub=true \
        -Dandroid-libbacktrace=disabled -Dgallium-drivers=radeonsi -Dvulkan-drivers= \
        -Dgallium-va=enabled -Dva-libs-path=/lib64 -Dvideo-codecs=jpegdec \
        -Dopengl=false -Dglx=disabled -Degl=disabled -Dgles1=disabled -Dgles2=disabled \
        -Dgbm=disabled -Dllvm=disabled -Damd-use-llvm=false \
        -Dvalgrind=disabled -Dlibunwind=disabled -Dzstd=disabled
fi
meson compile -C "$build/mesa" -j "${JOBS:-4}"
meson compile -C "$va_build" -j "${JOBS:-4}"
# Meson strips even skipped install targets, changing their timestamps. Stage that work
# in the build cache and publish only changed bytes.
DESTDIR="$build/install" meson install -C "$build/mesa" --no-rebuild --only-changed --strip
DESTDIR="$build/va-install" meson install -C "$va_build" --no-rebuild --only-changed --strip
"$tc/llvm-readelf" --dyn-syms --wide "$build/va-install/lib64/radeonsi_drv_video.so" \
    > "$build/va-symbols.txt"
grep -q 'GLOBAL.*DEFAULT.* __vaDriverInit_1_22$' "$build/va-symbols.txt" || {
    echo "RadeonSI VA driver does not export Google's VA-API 1.22 entry point" >&2
    exit 1
}
test -s "$va_sysroot/lib64/libdrm_amdgpu.so"
printf '%s\n' "$settings" > "$build/settings"
for file in libEGL_mesa.so libGLESv1_CM_mesa.so libGLESv2_mesa.so libgallium_dri.so \
        libvulkan_radeon.so libvulkan_intel_hasvk.so libgbm_mesa.so gbm/dri_gbm.so; do
    test -s "$build/install/lib64/$file"
    if ! cmp -s "$build/install/lib64/$file" "$out/install/lib64/$file"; then
        mkdir -p "$(dirname "$out/install/lib64/$file")"
        cp "$build/install/lib64/$file" "$out/install/lib64/$file.partial"
        mv "$out/install/lib64/$file.partial" "$out/install/lib64/$file"
    fi
done
file=radeonsi_drv_video.so
if ! cmp -s "$build/va-install/lib64/$file" "$out/install/lib64/$file"; then
    cp "$build/va-install/lib64/$file" "$out/install/lib64/$file.partial"
    mv "$out/install/lib64/$file.partial" "$out/install/lib64/$file"
fi
file=libdrm_amdgpu.so
if ! cmp -s "$va_sysroot/lib64/$file" "$out/install/lib64/$file"; then
    cp "$va_sysroot/lib64/$file" "$out/install/lib64/$file.partial"
    mv "$out/install/lib64/$file.partial" "$out/install/lib64/$file"
fi
(cd "$out/install" && find . -type f -name '*.so*' -print0 | sort -z | xargs -0 sha256sum) > "$out/manifest.partial"
if ! cmp -s "$out/manifest.partial" "$out/manifest"; then
    mv "$out/manifest.partial" "$out/manifest"
else
    rm "$out/manifest.partial"
fi
