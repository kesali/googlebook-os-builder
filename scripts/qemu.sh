#!/usr/bin/env bash
# Boot Googlebook OS in QEMU: our kernel, the Android initrd and the Android disk.
#
#   qemu.sh <bzImage> <initrd> <disk> <cmdline.txt> <log dir> <CPUs> <memory>
#
# VNC is published to localhost by builder.sh. The serial shell and QMP monitor use
# local Unix sockets in <log dir>, so boot tests can inspect the same VM as a human.
# Ctrl-C stops the VM; use Android's shutdown menu for an orderly shutdown.
set -euo pipefail
kernel=$1 initrd=$2 disk=$3 cmdline=$4 logs=$5 cpus=$6 memory=$7

if [ ! -w /dev/kvm ]; then
    echo "QEMU needs hardware virtualization (/dev/kvm); Android is too slow without it." >&2
    exit 1
fi
mkdir -p "$logs"
logs=$(realpath "$logs")
exec 9>"$disk.lock"
flock -n 9 || { echo "The Android disk is already in use." >&2; exit 1; }

# cmdline.txt is one argument per line with # comments; QEMU adds the serial console.
args=$(sed 's/#.*//' "$cmdline" | tr -s '[:space:]' ' ')
args+="console=ttyS1,115200 printk.devkmsg=on"

echo "VNC: localhost:${QEMU_VNC_PORT:-5900}. Kernel log: $logs/kernel.log. Ctrl-C stops QEMU."
if [ -f "$logs/kernel.log" ]; then mv "$logs/kernel.log" "$logs/kernel.previous.log"; fi
rm -f "$logs/console.sock" "$logs/monitor.sock"
# -cpu host: the guest sees this laptop's CPU, as Android will on the laptop itself.
# discard=unmap: blocks Android frees become holes again in the (sparse) disk file.
# -no-reboot: a reboot or kernel panic ends QEMU instead of looping.
exec qemu-system-x86_64 \
    -machine q35,accel=kvm -cpu host -smp "$cpus" -m "$memory" \
    -global ICH9-LPC.disable_s3=1 -global ICH9-LPC.disable_s4=1 \
    -nodefaults -display none -vnc 0.0.0.0:0 -no-reboot \
    -kernel "$kernel" -initrd "$initrd" -append "$args" \
    -drive if=none,id=disk,file="$disk",format=raw,discard=unmap \
    -device nvme,drive=disk,serial=DALI0001 \
    -device virtio-gpu-pci,xres=1280,yres=720 \
    -device virtio-keyboard-pci -device virtio-mouse-pci \
    -netdev user,id=network -device virtio-net-pci,netdev=network \
    -chardev socket,id=console,path="$logs/console.sock",server=on,wait=off \
    -serial chardev:console -serial file:"$logs/kernel.log" \
    -qmp unix:"$logs/monitor.sock",server=on,wait=off
