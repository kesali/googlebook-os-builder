#!/usr/bin/env python3
"""Check that our kernel exports every symbol Google's does, with the same CRC.

    kabi_check.py <google vmlinux.symvers> <our Module.symvers>

A symvers line is: CRC, symbol, module, export type[, namespace], tab-separated.
Each prebuilt module records the CRC of every kernel symbol it uses, and the
kernel refuses to load it if one differs ("disagrees about version of symbol").
So a single missing or changed symbol fails the build.
"""

import sys


def read(path):
    """Return {symbol: CRC}."""
    with open(path, encoding="utf-8") as symvers:
        return {line.split("\t")[1]: line.split("\t")[0] for line in symvers if line.strip()}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    google, ours = read(sys.argv[1]), read(sys.argv[2])
    missing = sorted(symbol for symbol in google if symbol not in ours)
    changed = sorted(symbol for symbol in google if symbol in ours and ours[symbol] != google[symbol])
    for symbol in missing[:20]:
        print(f"kABI: missing {symbol}", file=sys.stderr)
    for symbol in changed[:20]:
        print(f"kABI: CRC differs for {symbol}", file=sys.stderr)
    print(f"kABI: {len(google)} Google exports, {len(missing)} missing, {len(changed)} changed")
    if missing or changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
