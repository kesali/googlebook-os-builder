#!/usr/bin/env python3
"""Check our kernel configuration against Google's, before compiling.

    kconfig_check.py <google config> <our changes> <resolved .config>

Fails, saying why, unless:
1. every setting in <our changes> is in effect. Kconfig silently drops a
   setting whose dependencies are missing;
2. every built-in (=y) setting is Google's, apart from those in <our changes>.
   A built-in option can change the layout of kernel structures, which Google's
   prebuilt modules depend on. Extra modules (=m) are fine;
3. the compilers are Google's (the *_VERSION settings Kconfig reads from them).
   Other compilers give other symbol versions and Rust symbol names.
"""

import re
import sys

SETTING = re.compile(r"^(CONFIG_\w+)=(.*)$")
UNSET = re.compile(r"^# (CONFIG_\w+) is not set$")
TOOL_VERSION = re.compile(r"_VERSION(_TEXT)?$")


def read(path):
    """Return {symbol: value}; an unset option has the value "n"."""
    settings = {}
    with open(path, encoding="utf-8") as config:
        for line in config:
            line = line.rstrip("\n")
            if match := SETTING.match(line):
                settings[match[1]] = match[2]
            elif match := UNSET.match(line):
                settings[match[1]] = "n"
    return settings


def problems(google, changes, result):
    for symbol, wanted in changes.items():
        got = result.get(symbol, "n")
        if got != wanted:
            yield f"{symbol}: asked for {wanted}, got {got} (a dependency is missing?)"
    for symbol in sorted(google.keys() | result.keys()):
        was, now = google.get(symbol, "n"), result.get(symbol, "n")
        if was == now or symbol in changes:
            continue
        if "y" in (was, now):
            yield f"{symbol}: built-in setting changed from {was} to {now}; add it to the changes if intended"
        elif TOOL_VERSION.search(symbol):
            yield f"{symbol}: compiler differs from Google's\n    Google: {was}\n    ours:   {now}"


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    found = list(problems(read(sys.argv[1]), read(sys.argv[2]), read(sys.argv[3])))
    for problem in found:
        print(f"kernel config: {problem}", file=sys.stderr)
    if found:
        sys.exit(1)
    print("kernel config: Google's, plus only our changes")


if __name__ == "__main__":
    main()
