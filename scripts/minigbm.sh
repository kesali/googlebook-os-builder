#!/usr/bin/env bash
# Read: minigbm source, Android headers, NDK, Mesa's libdrm, Google libraries and AIDL.
# Write: ABI-checked allocator libraries, linked to Google's platform libc++.
#
#   minigbm.sh <source> <headers> <ndk> <mesa> <google> <aidl> <output>
set -euo pipefail
source=$(realpath "$1") headers=$(realpath "$2") ndk=$(realpath "$3")
mesa=$(realpath "$4") google=$(realpath "$5") aidl=$(realpath "$6") output=$(realpath -m "$7")
root=$(cd "$(dirname "$0")/.." && pwd)
tc=$ndk/toolchains/llvm/prebuilt/linux-x86_64/bin
sysroot=$(realpath "$mesa/sysroot")
key=$(printf '%s\n' "$source" "$ndk" "$sysroot" "$(cat "$headers/.ready")" | sha256sum | cut -c1-16)
build=$output/build-$key
mkdir -p "$build/gen" "$build/link" "$output"

# Link with the actual platform libraries, not executable stand-ins for missing NDK APIs.
for library in libc++ libcutils libdmabufheap; do
    dump.erofs --path="/lib64/$library.so" --cat "$google/super/vendor_a.img" > "$build/link/$library.so.partial"
    if ! cmp -s "$build/link/$library.so.partial" "$build/link/$library.so"; then
        mv "$build/link/$library.so.partial" "$build/link/$library.so"
    else
        rm "$build/link/$library.so.partial"
    fi
done
dump.erofs --path=/system/lib64/libsync.so --cat "$google/super/system_a.img" > "$build/link/libsync.so.partial"
if ! cmp -s "$build/link/libsync.so.partial" "$build/link/libsync.so"; then
    mv "$build/link/libsync.so.partial" "$build/link/libsync.so"
else
    rm "$build/link/libsync.so.partial"
fi

common=$headers/interfaces/common/aidl/aidl_api/android.hardware.common/2
graphics=$headers/interfaces/graphics/common/aidl/aidl_api/android.hardware.graphics.common/7
settings=$(cat "$0" "$headers/.ready" "$root/hardware/drivers/amdgpu/minigbm-platform-cxx.h" | sha256sum | cut -d' ' -f1)
if [ ! -f "$build/settings" ] || [ "$settings" != "$(cat "$build/settings")" ]; then
    for api in "$common" "$graphics"; do
        mapfile -t files < <(find "$api" -name '*.aidl' | LC_ALL=C sort)
        "$aidl" --lang=ndk --structured --stability=vintf --version="${api##*/}" \
            --hash="$(tail -n 1 "$api/.hash")" -I "$common" -I "$graphics" \
            -h "$build/gen" -o "$build/gen/src" "${files[@]}"
    done
    printf '%s\n' "$settings" > "$build/settings"
fi

includes="-I$source -I$source/external -I$build/gen -I$sysroot/include -I$sysroot/include/libdrm"
for directory in core/libcutils/include core/libsystem/include core/libsync/include \
        logging/liblog/include hardware/include_all native/libs/nativewindow/include \
        native/libs/nativebase/include native/libs/arect/include native/libs/binder/ndk/include_cpp \
        native/libs/binder/ndk/include_ndk dmabuf/include base/include; do
    includes+=" -I$headers/$directory"
done
flags="-O2 -fPIC -Wall -Wno-unused-parameter -Wno-sign-compare -Wno-unused-function"
flags+=" -DDRV_MESA_AMDGPU -DDRV_I915 -DDRV_XE -DHAS_DMABUF_SYSTEM_HEAP -DANDROID_API_LEVEL=37"
flags+=" -D_GNU_SOURCE=1 -D_FILE_OFFSET_BITS=64 -D__ANDROID_VNDK__ -D__ANDROID_VENDOR__"
cat > "$build/build.ninja.partial" <<EOF
rule cc
  command = $tc/x86_64-linux-android35-clang $flags $includes -std=gnu11 -MMD -MF \$out.d -c \$in -o \$out
  depfile = \$out.d
  deps = gcc
rule cxx
  command = $tc/x86_64-linux-android35-clang++ $flags $includes -std=c++20 -fvisibility-inlines-hidden -include $root/hardware/drivers/amdgpu/minigbm-platform-cxx.h -MMD -MF \$out.d -c \$in -o \$out
  depfile = \$out.d
  deps = gcc
rule link
  command = $tc/x86_64-linux-android35-clang++ -shared -nostdlib++ -Wl,-soname,\$out -Wl,--as-needed -Wl,--no-undefined -o \$out \$in $sysroot/lib64/libdrm.a -L$build/link -lc++ -lcutils -llog -ldl \$libraries && $tc/llvm-strip --strip-unneeded \$out
EOF
core=""
for name in backend_mock dma_heap drv drv_array_helpers drv_helpers dumb_driver i915 mediatek \
        msm rockchip vc4 virtgpu virtgpu_cross_domain virtgpu_virgl xe; do
    printf 'build %s.o: cc %s/%s.c\n' "$name" "$source" "$name" >> "$build/build.ninja.partial"
    core+=" $name.o"
done
for name in gbm_mesa_driver gbm_mesa_internals; do
    printf 'build %s.o: cxx %s/gbm_mesa_driver/%s.cpp\n' "$name" "$source" "$name" >> "$build/build.ninja.partial"
    core+=" $name.o"
done
gralloc=""
for name in cros_gralloc_buffer cros_gralloc_driver cros_gralloc_helpers; do
    printf 'build %s.o: cxx %s/cros_gralloc/%s.cc\n' "$name" "$source" "$name" >> "$build/build.ninja.partial"
    gralloc+=" $name.o"
done
for name in gbm gbm_helpers minigbm_helpers; do
    printf 'build %s.o: cc %s/%s.c\n' "$name" "$source" "$name" >> "$build/build.ninja.partial"
done
cat >> "$build/build.ninja.partial" <<EOF
build gbm_mesa_wrapper.o: cc $source/gbm_mesa_driver/gbm_mesa_wrapper.c
build libminigbm_gralloc.so: link $core $gralloc | $sysroot/lib64/libdrm.a $build/link/libc++.so $build/link/libcutils.so $build/link/libdmabufheap.so $build/link/libsync.so
  libraries = -ldmabufheap -lsync -lnativewindow
build libgbm.so: link $core gbm.o gbm_helpers.o minigbm_helpers.o | $sysroot/lib64/libdrm.a $build/link/libc++.so $build/link/libcutils.so
build libgbm_mesa_wrapper.so: link gbm_mesa_wrapper.o | $sysroot/lib64/libdrm.a
default libminigbm_gralloc.so libgbm.so libgbm_mesa_wrapper.so
EOF
if ! cmp -s "$build/build.ninja.partial" "$build/build.ninja"; then
    mv "$build/build.ninja.partial" "$build/build.ninja"
else
    rm "$build/build.ninja.partial"
fi
ninja -C "$build" -j "${JOBS:-4}"

(cd "$build" && sha256sum libminigbm_gralloc.so libgbm.so libgbm_mesa_wrapper.so) > "$build/manifest"
# A new Google image can change its clients even if our libraries stayed identical.
sha256sum "$google/super/vendor_a.img" "$root/tools/minigbm_abi.py" "$build/manifest" > "$build/abi-inputs.partial"
if ! cmp -s "$build/abi-inputs.partial" "$build/abi-inputs"; then
    python3 "$root/tools/minigbm_abi.py" "$google/super/vendor_a.img" "$build"
    mv "$build/abi-inputs.partial" "$build/abi-inputs"
else
    rm "$build/abi-inputs.partial"
fi
if ! cmp -s "$build/manifest" "$output/manifest"; then
    for library in libminigbm_gralloc.so libgbm.so libgbm_mesa_wrapper.so; do
        cp "$build/$library" "$output/$library.partial"
        mv "$output/$library.partial" "$output/$library"
    done
    cp "$build/manifest" "$output/manifest.partial"
    mv "$output/manifest.partial" "$output/manifest"
fi
