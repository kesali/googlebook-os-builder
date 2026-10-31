#!/usr/bin/env bash
# Read: GRUB source + small embedded config. Write: a source-built removable-media EFI loader.
set -euo pipefail
source=$(realpath "$1") build=$(realpath -m "$2") config=$(realpath "$3") script=$(realpath "$0")
# The 2.12 release tarball omits this intentionally empty file (upstream ChangeLog, 2023-12-05).
if [ ! -e "$source/grub-core/extra_deps.lst" ]; then
    touch "$source/grub-core/extra_deps.lst"
fi
mkdir -p "$build"
cd "$build"
if [ ! -f Makefile ]; then
    AWK=gawk "$source/configure" --target=x86_64 --with-platform=efi \
        --disable-werror --disable-nls --disable-device-mapper --disable-libzfs \
        --disable-grub-mount --disable-grub-mkfont --disable-grub-themes
fi
make --no-print-directory AWK=gawk -j"${JOBS:-4}"
inputs=$({ cat "$config" "$script"; sha256sum grub-mkstandalone grub-core/*.mod; } | sha256sum | cut -d' ' -f1)
if [ -f efi.inputs ] && [ "$inputs" = "$(cat efi.inputs)" ] && [ -s BOOTX64.EFI ]; then
    exit 0
fi
./grub-mkstandalone -O x86_64-efi -d grub-core \
    --modules="part_gpt fat normal linux configfile regexp probe serial test" \
    --locales="" --fonts="" --output=BOOTX64.EFI.partial \
    "boot/grub/grub.cfg=$config"
if ! cmp -s BOOTX64.EFI.partial BOOTX64.EFI; then
    mv BOOTX64.EFI.partial BOOTX64.EFI
else
    rm BOOTX64.EFI.partial
fi
printf '%s\n' "$inputs" > efi.inputs
