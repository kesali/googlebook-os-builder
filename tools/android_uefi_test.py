#!/usr/bin/env python3
"""Test Android's laptop boot chain on a disposable image, never a physical drive.

OVMF and GRUB load the disk's own kernel and initrd. Two runs check the laptop's
DRM log console (virtio-vga) and graphical Android over USB (virtio-gpu-pci).
The latter has no firmware framebuffer; this does not prove a simpledrm-to-GPU
handoff. Both runs add only serial logging to the copy's text menu and require a
writable NVMe decoy to stay hidden and byte-identical. The original is only read.
"""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from android_console import command
from android_smoke import qmp, verify


def copy_disk(image, destination):
    if image.is_symlink() or not image.is_file():
        raise ValueError("UEFI tests accept only a regular disk image, never a device/symlink")
    with Path(str(image) + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Stop QEMU before copying its disk") from error
        subprocess.run(["cp", "--reflink=auto", "--sparse=always", str(image), str(destination)], check=True)


def serial_menu(text):
    lines = text.splitlines()
    entries = [index for index, line in enumerate(lines) if line.lstrip().startswith("linux ")]
    if len(entries) != 1:
        raise ValueError("Expected exactly one Android linux entry")
    index = entries[0]
    words = lines[index].split()
    if "initcall_blacklist=nvme_init" not in words:
        raise ValueError("The laptop menu must hide the internal NVMe")
    if "console=drm_log" not in words:
        raise ValueError("The laptop menu must enable its DRM log console")
    if any(word.startswith("console=") and word != "console=drm_log" for word in words):
        raise ValueError("The laptop menu unexpectedly selects another console")
    lines[index] += " console=ttyS1,115200"
    return "\n".join(lines) + "\n"


def prepare_menu(disk, work, logs):
    table = json.loads(subprocess.check_output(["sfdisk", "--json", str(disk)]))["partitiontable"]
    partitions = [p for p in table["partitions"] if p.get("name") == "EFI-SYSTEM"]
    if table["label"] != "gpt" or table["sectorsize"] != 512 or len(partitions) != 1:
        raise ValueError("Expected one EFI-SYSTEM in a 512-byte-sector GPT")
    fat = f"{disk}@@{partitions[0]['start'] * 512}"
    menu = work / "grub.cfg"
    subprocess.run(["mcopy", "-i", fat, "::/gbos-builder/grub.cfg", str(menu)], check=True)
    menu.write_text(serial_menu(menu.read_text()))
    shutil.copyfile(menu, logs / "grub.cfg")
    subprocess.run(["mcopy", "-o", "-i", fat, str(menu), "::/gbos-builder/grub.cfg"], check=True)


def qemu_command(work, logs, cpus, memory, graphical):
    gpu = "virtio-gpu-pci" if graphical else "virtio-vga"
    return [
        "qemu-system-x86_64", "-machine", "q35,accel=kvm", "-cpu", "host",
        "-smp", cpus, "-m", memory,
        "-global", "ICH9-LPC.disable_s3=1", "-global", "ICH9-LPC.disable_s4=1",
        "-nodefaults", "-display", "none", "-no-reboot",
        "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
        "-drive", f"if=pflash,format=raw,file={work / 'OVMF_VARS.fd'}",
        "-drive", f"if=none,id=stick,format=raw,file={work / 'usb.img'},discard=unmap",
        "-device", "qemu-xhci,id=xhci",
        # Debian's OVMF cannot discover QEMU's UAS-only device; use USB bulk-only transport.
        "-device", "usb-storage,bus=xhci.0,drive=stick,bootindex=1",
        "-drive", f"if=none,id=internal,format=raw,file={work / 'nvme.img'}",
        "-device", "nvme,id=decoy,drive=internal,serial=GBOS-BUILDER-DECOY,addr=3",
        # Google's sysfs_gpu label covers 00:02.0, also used by the direct-kernel VM.
        "-device", f"{gpu},addr=2,xres=1280,yres=720",
        "-device", "virtio-keyboard-pci", "-device", "virtio-mouse-pci",
        "-netdev", "user,id=network", "-device", "virtio-net-pci,netdev=network",
        "-chardev", f"socket,id=console,path={logs / 'console.sock'},server=on,wait=off",
        "-serial", "chardev:console", "-serial", f"file:{logs / 'kernel.log'}",
        "-qmp", f"unix:{logs / 'monitor.sock'},server=on,wait=off",
    ]


def early_screen(logs, process):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"QEMU exited; see {logs / 'runner.log'}")
        kernel = logs / "kernel.log"
        if kernel.exists() and "Run /init as init process" in kernel.read_text(errors="replace"):
            # Freeze before Android starts trying to own the display.
            qmp(logs / "monitor.sock", "stop")
            try:
                qmp(logs / "monitor.sock", "screendump",
                    {"filename": str(logs / "early-screen.png"), "format": "png"})
            finally:
                qmp(logs / "monitor.sock", "cont")
            return
        time.sleep(0.02)
    raise TimeoutError("UEFI/GRUB did not reach Android's init within 120 seconds")


def check_storage(kernel, cmdline, blocks, controllers, boot_path, graphical=False):
    blacklists = [word.split("=", 1)[1] for word in cmdline.split()
                  if word.startswith("initcall_blacklist=")]
    if blacklists != ["nvme_init"]:
        raise RuntimeError("The booted kernel lost the laptop's NVMe blacklist")
    if controllers.strip() or re.search(r"\bnvme\d", kernel + "\n" + blocks):
        raise RuntimeError("Linux enumerated the decoy NVMe")
    if not re.search(r"/usb\d+/.*/block/sd[a-z]+/sd[a-z]+\d+$", boot_path.strip()):
        raise RuntimeError(f"Android did not find EFI-SYSTEM on USB: {boot_path}")
    if graphical and "Initialized simpledrm" in kernel:
        raise RuntimeError("The graphical test unexpectedly has a firmware framebuffer")
    if not graphical and ("Initialized simpledrm" not in kernel or "console [drm_log" not in kernel):
        raise RuntimeError("The firmware framebuffer did not register the DRM log console")


def verify_storage(logs, graphical):
    console = logs / "console.sock"
    cmdline = command(console, "cat /proc/cmdline")
    blocks = command(console, "ls -1 /sys/class/block")
    controllers = command(console, "ls -1 /sys/class/nvme")
    partition = command(console, "readlink -f /dev/block/by-name/EFI-SYSTEM").strip()
    if not re.fullmatch(r"/dev/block/sd[a-z]+\d+", partition):
        raise RuntimeError(f"Unexpected EFI-SYSTEM device: {partition}")
    boot_path = command(console, f"readlink -f /sys/class/block/{Path(partition).name}")
    (logs / "storage.txt").write_text(
        f"Command line:\n{cmdline}\nBlock devices:\n{blocks}\nNVMe controllers:\n{controllers}"
        f"\nEFI-SYSTEM:\n{partition}\n{boot_path}")
    check_storage((logs / "kernel.log").read_text(errors="replace"),
                  cmdline, blocks, controllers, boot_path, graphical)
    pci = qmp(logs / "monitor.sock", "query-pci")
    (logs / "pci.json").write_text(json.dumps(pci, indent=2) + "\n")
    if not any(device["qdev_id"] == "decoy" for bus in pci for device in bus["devices"]):
        raise RuntimeError("QEMU did not expose the decoy NVMe controller")


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stop_vm(process, logs):
    if process.poll() is None:
        try:
            qmp(logs / "monitor.sock", "quit")
        except (OSError, RuntimeError) as error:
            print(f"QMP shutdown failed ({error}); terminating this QEMU process.", flush=True)
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def wait_for_shell(logs, process):
    deadline = time.monotonic() + 120
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("QEMU exited before the serial shell started")
        try:
            if command(logs / "console.sock", "getenforce", timeout=5).strip() == "Enforcing":
                return
        except (OSError, RuntimeError) as error:
            last_error = str(error)
        time.sleep(2)
    raise TimeoutError(f"Android's enforcing serial shell did not start: {last_error}")


def run(image, output, cpus, memory, graphical):
    if not os.access("/dev/kvm", os.W_OK):
        raise ValueError("Android's UEFI test needs /dev/kvm")
    # A fresh evidence directory prevents an old screenshot from passing for this run.
    mode = "graphics" if graphical else "console"
    logs = Path(tempfile.mkdtemp(prefix=f"android-uefi-{mode}-", dir=output)).resolve()
    print(f"UEFI evidence: {logs}", flush=True)
    with tempfile.TemporaryDirectory(prefix="work-", dir=logs) as temporary:
        work = Path(temporary)
        copy_disk(image, work / "usb.img")
        prepare_menu(work / "usb.img", work, logs)
        shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", work / "OVMF_VARS.fd")
        decoy = work / "nvme.img"
        decoy.write_bytes(os.urandom(16 << 20))
        before = file_hash(decoy)
        invocation = qemu_command(work, logs, cpus, memory, graphical)
        (logs / "command.json").write_text(json.dumps(invocation, indent=2) + "\n")
        with (logs / "runner.log").open("w") as runner:
            process = subprocess.Popen(invocation, stdout=runner, stderr=subprocess.STDOUT)
            try:
                if graphical:
                    verify(logs, process)
                else:
                    early_screen(logs, process)
                    wait_for_shell(logs, process)
                    qmp(logs / "monitor.sock", "screendump",
                        {"filename": str(logs / "screen.png"), "format": "png"})
                verify_storage(logs, graphical)
                try:
                    command(logs / "console.sock", "sync; setprop sys.powerctl shutdown", timeout=5)
                    process.wait(timeout=15)
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                    print(f"Guest shutdown incomplete ({error}); stopping the disposable VM.", flush=True)
            finally:
                if process.poll() is None and (logs / "monitor.sock").exists():
                    try:
                        (logs / "logcat.txt").write_text(
                            command(logs / "console.sock", "logcat -d -t 300", timeout=10))
                    except (OSError, RuntimeError) as error:
                        print(f"Could not collect Android logs: {error}", flush=True)
                    try:
                        qmp(logs / "monitor.sock", "screendump",
                            {"filename": str(logs / "last-screen.png"), "format": "png"})
                    except (OSError, RuntimeError) as error:
                        print(f"Could not capture final screen: {error}", flush=True)
                stop_vm(process, logs)
                after = file_hash(decoy)
                (logs / "decoy-sha256.txt").write_text(f"before {before}\nafter  {after}\n")
                if before != after:
                    raise RuntimeError("The decoy NVMe was modified")
    print(f"PASS ({mode}): UEFI -> GRUB -> Android on USB; NVMe hidden and unchanged. "
          f"Inspect screenshots in {logs}.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("cpus")
    parser.add_argument("memory")
    parser.add_argument("--image", type=Path, help="Disk image to test instead of OUT/gbos-builder/disk.img")
    args = parser.parse_args()
    try:
        for graphical in (False, True):
            run(args.image or args.out / "gbos-builder/disk.img", args.out, args.cpus, args.memory, graphical)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"android-uefi-check: {error}\n")


if __name__ == "__main__":
    main()
