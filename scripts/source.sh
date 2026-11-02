#!/usr/bin/env bash
# Read: verified release archive and optional patches. Write: a private editable source tree.
#
#   scripts/source.sh <archive> <destination> [patch ...]
set -euo pipefail
archive=$1 destination=$2
mkdir -p "$(dirname "$destination")"
temporary=$(mktemp -d "$destination.partial.XXXXXX")
trap 'rm -rf "$temporary"' EXIT
tar -xf "$archive" --strip-components=1 -C "$temporary"
for source_patch in "${@:3}"; do
    patch --batch --fuzz=0 -d "$temporary" -p1 < "$source_patch"
done
if [ -e "$destination" ]; then
    echo "Refusing to replace source tree $destination; preserve local edits first." >&2
    exit 1
fi
touch "$temporary/.ready"
mv "$temporary" "$destination"
