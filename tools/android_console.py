#!/usr/bin/env python3
"""Run a command through Google's serial shell, with explicit result framing and timeout."""

import argparse
from pathlib import Path
import re
import socket
import time
import uuid


def command(path, text, timeout=30):
    token = uuid.uuid4().hex
    start = f"GBOS_BUILDER_START_{token}"
    end = f"GBOS_BUILDER_END_{token}"
    line = f"printf '\\n{start}\\n'; {text}; result=$?; printf '\\n{end}:%s\\n' \"$result\"\n"
    deadline = time.monotonic() + timeout
    output = bytearray()
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(timeout)
        connection.connect(str(path))
        connection.sendall(line.encode())
        while time.monotonic() < deadline:
            connection.settimeout(max(0.1, deadline - time.monotonic()))
            block = connection.recv(65536)
            if not block:
                raise OSError("Android serial console disconnected")
            output.extend(block)
            decoded = output.decode(errors="replace").replace("\r", "")
            match = re.search(rf"\n{start}\n(.*?)\n{end}:(\d+)\n", decoded, re.S)
            if match:
                if int(match[2]):
                    raise RuntimeError(f"Android command failed ({match[2]}):\n{match[1]}")
                return match[1]
    raise TimeoutError(f"Android command timed out: {text}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("socket", type=Path)
    parser.add_argument("command")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    if not args.command.strip():
        parser.error("Supply COMMAND, for example COMMAND='getprop sys.boot_completed'")
    try:
        print(command(args.socket, args.command, args.timeout))
    except (OSError, RuntimeError, TimeoutError) as error:
        parser.exit(1, f"android-console: {error}\n")


if __name__ == "__main__":
    main()
