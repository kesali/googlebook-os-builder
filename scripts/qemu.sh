#!/usr/bin/env bash
# Boot Googlebook OS in QEMU: our kernel, the Android initrd and the Android disk.
#
#   qemu.sh <bzImage> <initrd> <disk> <cmdline.txt> <log dir> <CPUs> <memory>
#
# This terminal becomes Android's serial shell (ttyS0; Google's apgetty starts it once
# Android is up). The kernel log goes to <log dir>/kernel.log (ttyS1).
# Quit: Ctrl-A then X. Ctrl-A then C switches to the QEMU monitor and back.
set -euo pipefail
kernel=$1 initrd=$2 disk=$3 cmdline=$4 logs=$5 cpus=$6 memory=$7

if [ ! -w /dev/kvm ]; then
    echo "QEMU needs hardware virtualization (/dev/kvm); Android is too slow without it." >&2
    exit 1
fi
mkdir -p "$logs"

# cmdline.txt is one argument per line with # comments; QEMU adds the serial console.
args=$(sed 's/#.*//' "$cmdline" | tr -s '[:space:]' ' ')
args+="console=ttyS1,115200 printk.devkmsg=on"

echo "Kernel log: $logs/kernel.log. Android's shell appears here. Quit: Ctrl-A X."
# -cpu host: the guest sees this laptop's CPU, as Android will on the laptop itself.
# discard=unmap: blocks Android frees become holes again in the (sparse) disk file.
# -no-reboot: a reboot or kernel panic ends QEMU instead of looping.
exec qemu-system-x86_64 \
    -machine q35,accel=kvm -cpu host -smp "$cpus" -m "$memory" \
    -nodefaults -display none -no-reboot \
    -kernel "$kernel" -initrd "$initrd" -append "$args" \
    -drive if=none,id=disk,file="$disk",format=raw,discard=unmap \
    -device nvme,drive=disk,serial=DALI0001 \
    -serial mon:stdio -serial file:"$logs/kernel.log"
