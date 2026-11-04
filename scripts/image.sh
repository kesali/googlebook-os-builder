#!/usr/bin/env bash
# Read: build bundle. Write: a NEW GPT/UEFI USB image, without root, loop devices or mounts.
set -euo pipefail
bundle=$(realpath "$1") output=$(realpath -m "$2")
tools=$(cd "$(dirname "$0")/../tools" && pwd)
mkdir -p "$(dirname "$output")"
if [ -L "$2" ] || { [ -e "$output" ] && [ ! -f "$output" ]; }; then
    echo "Image output must be a regular file, never a device or symlink." >&2
    exit 1
fi
work=$(mktemp -d "$(dirname "$output")/image.XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir "$work/files"
python3 "$tools/deploy.py" stage "$bundle" "$work/files"
truncate -s 512M "$work/esp.img"
mkfs.vfat -F 32 -n GBOS-BOOT "$work/esp.img"
mcopy -s -i "$work/esp.img" "$work/files/EFI" "$work/files/gbos-builder" ::

# A 1 MiB-aligned ESP, plus space for both GPT headers. Everything is assembled
# from source-built files; no offsets inside executable binaries are patched.
truncate -s 514M "$work/usb.img"
sfdisk "$work/usb.img" <<'EOF'
label: gpt
unit: sectors
start=2048, size=1048576, type=U, name="GBOS-BOOT"
EOF
dd if="$work/esp.img" of="$work/usb.img" bs=1M seek=1 conv=notrunc,sparse status=none
mv "$work/usb.img" "$output"
echo "Image ready: $output (diagnostic shell, NOT an Android desktop)"
