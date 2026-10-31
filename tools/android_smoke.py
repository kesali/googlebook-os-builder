#!/usr/bin/env python3
"""Require a stable, graphical Android boot, not merely a kernel/serial-shell boot."""

import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

from android_console import command


def check_scanout(path):
    header = path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n" or len(header) != 24:
        raise RuntimeError("QEMU did not capture a PNG scanout")
    size = struct.unpack(">II", header[16:24])
    if size != (1280, 720):
        raise RuntimeError(f"QEMU scanout is {size}, not the requested 1280x720 display")


def qmp(path, execute, arguments=None):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(15)
        connection.connect(str(path))
        stream = connection.makefile("rwb", buffering=0)
        greeting = json.loads(stream.readline())
        if "QMP" not in greeting:
            raise RuntimeError(f"Invalid QMP greeting: {greeting}")
        for request in ({"execute": "qmp_capabilities"}, {"execute": execute, "arguments": arguments or {}}):
            stream.write(json.dumps(request).encode() + b"\n")
            while True:
                response = json.loads(stream.readline())
                if "error" in response:
                    raise RuntimeError(f"QMP failed: {response['error']}")
                if "return" in response:
                    break
        return response["return"]


def verify(logs, process):
    console = logs / "console.sock"
    deadline = time.monotonic() + 600
    while not console.exists():
        if process.poll() is not None:
            raise RuntimeError(f"QEMU exited; see {logs / 'runner.log'}")
        if time.monotonic() > deadline:
            raise TimeoutError("QEMU serial socket did not appear")
        time.sleep(1)
    # Wait for the actual shell to start; connecting early can lose a command before apgetty.
    time.sleep(10)
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"QEMU exited; see {logs / 'runner.log'}")
        try:
            state = command(console, "getprop sys.boot_completed; "
                            "if pidof bootanimation > /dev/null; then echo animating; else echo ready; fi",
                            timeout=15).splitlines()
            if state == ["1", "ready"]:
                break
        except (OSError, RuntimeError) as error:
            last_error = str(error)
        time.sleep(5)
    else:
        raise TimeoutError(f"Android did not complete boot and leave the boot animation. {last_error}")

    # SELinux hides these HALs' init.svc properties from the serial shell.
    processes = ("pidof system_server; pidof surfaceflinger; "
                 "pidof android.hardware.security.keymint-service; "
                 "pidof android.hardware.gatekeeper-service")
    before = command(console, processes).strip()
    time.sleep(30)
    after = command(console, processes).strip()
    if len(before.splitlines()) != 4 or not all(pid.isdigit() for pid in before.splitlines()) or before != after:
        raise RuntimeError(f"Android processes restarted during the stability window: {before!r} -> {after!r}")
    state = command(console, "getprop sys.boot_completed; getenforce")
    if state.splitlines() != ["1", "Enforcing"]:
        raise RuntimeError(f"Android security/startup state is not healthy:\n{state}")
    graphics = command(console, "dumpsys SurfaceFlinger", timeout=60)
    (logs / "surfaceflinger.txt").write_text(graphics)
    if "softpipe" not in graphics.lower():
        raise RuntimeError("SurfaceFlinger did not report the source-built softpipe renderer")
    qmp(logs / "monitor.sock", "screendump", {"filename": str(logs / "screen.png"), "format": "png"})
    check_scanout(logs / "screen.png")
    (logs / "boot-state.txt").write_text(
        state + "\nStable PIDs (system_server, SurfaceFlinger, KeyMint, Gatekeeper):\n" + after + "\n")
    print("PASS: boot_completed=1; stable system_server/SurfaceFlinger; software KeyMint/Gatekeeper; SELinux enforcing; Mesa softpipe.")


def main():
    out = Path(sys.argv[1]).resolve()
    logs = out / "qemu"
    logs.mkdir(exist_ok=True)
    console = logs / "console.sock"
    with (logs / "runner.log").open("w") as output:
        process = subprocess.Popen([
            "bash", "scripts/qemu.sh", str(out / "gki/bzImage"), str(out / "android/initrd.img"),
            str(out / "android/disk.img"), "android/cmdline.txt", str(logs), sys.argv[2], sys.argv[3],
        ], stdout=output, stderr=subprocess.STDOUT)
        try:
            verify(logs, process)
        finally:
            if process.poll() is None:
                try:
                    (logs / "logcat.txt").write_text(command(console, "logcat -b all -d -t 1000", timeout=30))
                    command(console, "sync; setprop sys.powerctl shutdown", timeout=5)
                except (OSError, RuntimeError):
                    print("VM shutdown/diagnostic collection did not complete; stopping QEMU.", file=sys.stderr)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == "__main__":
    main()
