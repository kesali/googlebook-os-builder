#!/usr/bin/env python3
"""UEFI-boot a disposable copy of the real USB image, using an AVX2-only QEMU CPU."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    image, output = map(lambda value: Path(value).resolve(), sys.argv[1:])
    log = output / "boot-test.log"
    with tempfile.TemporaryDirectory(prefix="boot-test-", dir=output) as temporary:
        work = Path(temporary)
        disk = work / "usb.img"
        subprocess.run(["cp", "--reflink=auto", "--sparse=always", str(image), str(disk)], check=True)
        # Test mode changes only the text menu in this disposable copy.
        fat = f"{disk}@@1048576"
        menu = work / "grub.cfg"
        subprocess.run(["mcopy", "-i", fat, "::/dali/grub.cfg", str(menu)], check=True)
        text = menu.read_text()
        if text.count("dali.test=0") != 1:
            raise ValueError("Expected one diagnostic menu entry")
        menu.write_text(text.replace("dali.test=0", "dali.test=1"))
        subprocess.run(["mcopy", "-o", "-i", fat, str(menu), "::/dali/grub.cfg"], check=True)
        variables = work / "OVMF_VARS.fd"
        shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", variables)
        command = [
            "qemu-system-x86_64", "-machine", "q35", "-accel", "tcg",
            "-cpu", "Skylake-Client", "-m", "1024", "-smp", "2",
            "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
            "-drive", f"if=pflash,format=raw,file={variables}",
            "-drive", f"if=none,id=stick,format=raw,file={disk}",
            "-device", "qemu-xhci", "-device", "usb-storage,drive=stick,bootindex=1",
            "-display", "none", "-serial", "stdio", "-monitor", "none", "-nic", "none", "-no-reboot",
        ]
        try:
            result = subprocess.run(command, capture_output=True, timeout=180)
        except subprocess.TimeoutExpired as error:
            log.write_bytes((error.stdout or b"") + (error.stderr or b""))
            raise SystemExit(f"UEFI boot timed out; see {log}") from error
        log.write_bytes(result.stdout + result.stderr)
        text = log.read_text(errors="replace")
        required = (
            "DALI_DIAGNOSTIC_READY", "ISA_SMOKE_OK",
            "churro-vexemu: gf2p8mulb", "churro-vexemu: vpdpbusd",
        )
        if result.returncode or any(marker not in text for marker in required):
            raise SystemExit(f"UEFI boot/self-test failed; see {log}")
        subprocess.run(["mcopy", "-i", fat, "::/logs/kernel.log", str(work / "kernel.log")], check=True)
        if "ISA_SMOKE_OK" not in (work / "kernel.log").read_text():
            raise SystemExit("Kernel log was not persisted on the USB image")
        print(f"PASS: UEFI -> GRUB -> source-built kernel -> USB discovery -> GFNI/VNNI emulation -> saved logs -> poweroff. Log: {log}")


if __name__ == "__main__":
    main()
