#!/usr/bin/env bash
# Read: kernel source, Google's kernel (config, certificates, release string), Google's
# symbol list, our config changes, Google's toolchain. Write: <out>/bzImage, <out>/modules/.
#
#   gki-kernel.sh <source> <out> <toolchain> <google kernel> <google symvers> <changes.config>
#
# Same source, configuration, compilers and release string as Google's build: the
# result loads Google's prebuilt modules (ramdisks, system_dlkm, vendor_dlkm) and
# the extra drivers the changes add. Kbuild runs each time and is incremental.
set -euo pipefail
source=$(realpath "$1") out=$(realpath -m "$2") toolchain=$(realpath "$3")
google=$(realpath "$4") google_symvers=$(realpath "$5") changes=$(realpath "$6")
tools=$(cd "$(dirname "$0")/../tools" && pwd)
build=$out/build
release=$(sed -nE 's/^Linux version ([^ ]+) .*/\1/p' "$google/version.txt")
mkdir -p "$build"

export PATH="$toolchain/clang/bin:$toolchain/rust/bin:$toolchain/bindgen:$toolchain/pahole:$PATH"
export LIBCLANG_PATH=$toolchain/clang/lib # bindgen reads C headers with Google's clang
# Rust symbol names contain a hash of the compiler's version string. Google's build fixes
# that string (Kleaf's kernel_env.bzl), so the Rust symbols we export have Google's names.
export RUSTC_FORCE_RUSTC_VERSION=rustc-android
export KBUILD_BUILD_USER=dali KBUILD_BUILD_HOST=builder
export KBUILD_BUILD_TIMESTAMP='2026-10-01 00:00:00 UTC'
# KERNELRELEASE: Google's string, not one made from Git; module vermagic must match it.
# KBUILD_GENDWARFKSYMS_STABLE: compute symbol CRCs the way Google's build does.
mk=(make --no-print-directory -C "$source" O="$build" ARCH=x86_64 LLVM=1 LLVM_IAS=1
    KERNELRELEASE="$release" KBUILD_GENDWARFKSYMS_STABLE=1 -j"${JOBS:-4}")

# Configure only when an input changed; a new .config can rebuild a lot.
config_hash=$(cat "$google/config" "$changes" "$0" | sha256sum | cut -d' ' -f1)
if [ ! -f "$build/config.inputs" ] || [ "$config_hash" != "$(cat "$build/config.inputs")" ]; then
    python3 "$tools/kernel_certs.py" "$google/vmlinux" "$build/google-certs.pem"
    # Names of signed modules whose symbols unsigned modules may not replace. Every
    # module we load is signed, by Google or by this build, so the list stays empty.
    : > "$build/protected_module_names_list"
    cp "$google/config" "$build/.config"
    "$source/scripts/kconfig/merge_config.sh" -m -O "$build" "$build/.config" "$changes"
    "${mk[@]}" olddefconfig
    python3 "$tools/kconfig_check.py" "$google/config" "$changes" "$build/.config"
    printf '%s\n' "$config_hash" > "$build/config.inputs"
fi

"${mk[@]}" bzImage modules
[ "$(cat "$build/include/config/kernel.release")" = "$release" ] || {
    echo "Kernel release is not Google's $release" >&2
    exit 1
}
python3 "$tools/kabi_check.py" "$google_symvers" "$build/Module.symvers"

rm -rf "$out/modules.partial"
"${mk[@]}" INSTALL_MOD_PATH="$out/modules.partial" INSTALL_MOD_STRIP=1 modules_install
rm -rf "$out/modules"
mv "$out/modules.partial" "$out/modules"
if ! cmp -s "$build/arch/x86/boot/bzImage" "$out/bzImage"; then
    cp "$build/arch/x86/boot/bzImage" "$out/bzImage.partial"
    mv "$out/bzImage.partial" "$out/bzImage"
fi
