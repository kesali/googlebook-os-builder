#!/usr/bin/env bash
# Read: an extracted vendor tree, its install.list and the platform's LLNDK library list.
# Check: every program and library we install links only to libraries the vendor partition
# has (lib64/) or the platform offers vendors (LLNDK); anything else fails at runtime.
#
#   check-vendor-libs.sh INSTALL_LIST ROOT LLNDK
set -euo pipefail
list=$1 root=$2 llndk=$3
for path in $(awk '!/^#/ && NF {print $1}' "$list"); do
    # readelf fails on files that are not ELF (scripts, XML, directories): they link nothing.
    libraries=$(readelf -d "$root/$path" 2>/dev/null | sed -n 's/.*(NEEDED).*\[\(.*\)\]$/\1/p') || continue
    for library in $libraries; do
        if [ ! -e "$root/lib64/$library" ] && ! grep -qxF "$library" "$llndk"; then
            echo "vendor/$path needs $library, which is in neither vendor lib64 nor the LLNDK" >&2
            exit 1
        fi
    done
done
