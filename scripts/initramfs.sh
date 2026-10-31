#!/usr/bin/env bash
# Read: static BusyBox, diagnostic init, ISA self-test. Write: reproducible gzip/newc initramfs.
set -euo pipefail
busybox=$(realpath "$1") init=$(realpath "$2") smoke=$(realpath "$3") output=$(realpath -m "$4")
mkdir -p "$(dirname "$output")"
root=$(mktemp -d "$(dirname "$output")/ramdisk.XXXXXX")
trap 'rm -rf "$root"' EXIT
mkdir -p "$root"/{bin,dev,proc,sys,tmp,boot}
cp "$busybox" "$root/bin/busybox"
cp "$smoke" "$root/bin/isa-smoke"
cp "$init" "$root/init"
chmod 755 "$root/init" "$root/bin/busybox" "$root/bin/isa-smoke"
for applet in $("$root/bin/busybox" --list); do
    [ "$applet" = busybox ] || ln -s busybox "$root/bin/$applet"
done
find "$root" -exec touch -h -d @0 {} +
(cd "$root" && find . -print0 | LC_ALL=C sort -z | cpio --null -o -H newc --owner=0:0 --reproducible) \
    | gzip -n > "$output.partial"
mv "$output.partial" "$output"
