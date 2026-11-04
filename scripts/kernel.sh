#!/usr/bin/env bash
# Read: editable kernel source + hardware config. Write: bzImage and resolved .config.
# Kbuild runs each time; it, not a wrapper stamp, tracks edits to the source tree.
set -euo pipefail
source=$(realpath "$1") build=$(realpath -m "$2") profile=$(realpath "$3")
mkdir -p "$build"
config_hash=$({ printf '%s\n' "$source"; cat "$profile" "$0"; } | sha256sum | cut -d' ' -f1)
export KBUILD_BUILD_USER=gbos-builder KBUILD_BUILD_HOST=builder
export KBUILD_BUILD_TIMESTAMP='2026-10-01 00:00:00 UTC'
mk=(make --no-print-directory -C "$source" O="$build" ARCH=x86_64 -j"${JOBS:-4}")

if [ ! -f "$build/config.inputs" ] || [ "$config_hash" != "$(cat "$build/config.inputs")" ]; then
    "${mk[@]}" x86_64_defconfig
    "$source/scripts/kconfig/merge_config.sh" -m -O "$build" "$build/.config" "$profile"
    "${mk[@]}" olddefconfig
    while read -r setting; do
        if [[ "$setting" = CONFIG_*=* ]] && ! grep -qxF "$setting" "$build/.config"; then
            echo "Required kernel setting not enabled: $setting" >&2
            exit 1
        fi
        if [[ "$setting" = "# CONFIG_"*" is not set" ]]; then
            symbol=${setting#\# }; symbol=${symbol% is not set}
            if grep -q "^$symbol=[ym]" "$build/.config"; then
                echo "Forbidden kernel setting enabled: $symbol" >&2
                exit 1
            fi
        fi
    done < "$profile"
    printf '%s\n' "$config_hash" > "$build/config.inputs"
fi
"${mk[@]}" bzImage
if ! cmp -s "$build/arch/x86/boot/bzImage" "$build/bzImage"; then
    cp "$build/arch/x86/boot/bzImage" "$build/bzImage.partial"
    mv "$build/bzImage.partial" "$build/bzImage"
fi
