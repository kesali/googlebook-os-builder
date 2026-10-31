#!/usr/bin/env bash
# Read: kernel source, Google's kernel (config, certificates, release string), Google's
# symbol list and ABI symbol list, our config changes, Google's toolchain.
# Write: <out>/bzImage.
#
#   gki-kernel.sh <source> <out> <toolchain> <google kernel> <google symvers> <google abi list> <changes.config>
#
# Same source, configuration, compilers and release string as Google's build, plus the
# instruction emulator: the result loads Google's prebuilt modules (ramdisks, system_dlkm,
# vendor_dlkm and the QEMU drivers). Kbuild runs each time and is incremental.
set -euo pipefail
source=$(realpath "$1") out=$(realpath -m "$2") toolchain=$(realpath "$3")
google=$(realpath "$4") google_symvers=$(realpath "$5") abi_list=$(realpath "$6") changes=$(realpath "$7")
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
# Google's build number (#1); otherwise Kbuild counts links and every relink changes the bytes.
export KBUILD_BUILD_VERSION=1
# KERNELRELEASE: Google's string, not one made from Git; module vermagic must match it.
# KBUILD_GENDWARFKSYMS_STABLE: compute symbol CRCs the way Google's build does.
mk=(make --no-print-directory -C "$source" O="$build" ARCH=x86_64 LLVM=1 LLVM_IAS=1
    KERNELRELEASE="$release" KBUILD_GENDWARFKSYMS_STABLE=1 -j"${JOBS:-4}")

# Configure only when an input changed; a new .config can rebuild a lot.
config_hash=$(cat "$google/config" "$abi_list" "$changes" "$0" | sha256sum | cut -d' ' -f1)
if [ ! -f "$build/config.inputs" ] || [ "$config_hash" != "$(cat "$build/config.inputs")" ]; then
    python3 "$tools/kernel_certs.py" "$google/vmlinux" "$build/google-certs.pem"
    # Names of signed modules whose exports unsigned modules may not replace. Google's build
    # lists its system_dlkm modules; ours is empty, so this safeguard is off.
    : > "$build/protected_module_names_list"
    # CONFIG_UNUSED_KSYMS_WHITELIST: the exports kept for (and usable by) unsigned modules.
    cp "$abi_list" "$build/abi_symbollist.raw"
    cp "$google/config" "$build/.config"
    "$source/scripts/kconfig/merge_config.sh" -m -O "$build" "$build/.config" "$changes"
    "${mk[@]}" olddefconfig
    python3 "$tools/kconfig_check.py" "$google/config" "$changes" "$build/.config"
    printf '%s\n' "$config_hash" > "$build/config.inputs"
fi

# Google's in-tree modules are compiled too, only to find which exports they use; they
# are not installed (Google's signed copies are in the image).
"${mk[@]}" bzImage modules
[ "$(cat "$build/include/config/kernel.release")" = "$release" ] || {
    echo "Kernel release is not Google's $release" >&2
    exit 1
}
python3 "$tools/kabi_check.py" "$google_symvers" "$build/Module.symvers"

if ! cmp -s "$build/arch/x86/boot/bzImage" "$out/bzImage"; then
    cp "$build/arch/x86/boot/bzImage" "$out/bzImage.partial"
    mv "$out/bzImage.partial" "$out/bzImage"
fi
