#!/usr/bin/env bash
# Read: URL + SHA-256. Write: one verified source download, never a partial target.
set -euo pipefail
url=$1 sha=$2 destination=$3
mkdir -p "$(dirname "$destination")"
if [ -f "$destination" ] && printf '%s  %s\n' "$sha" "$destination" | sha256sum --check --status; then
    exit 0
fi
temporary=$(mktemp "$destination.partial.XXXXXX")
trap 'rm -f "$temporary"' EXIT
curl --fail --location --retry 3 --output "$temporary" "$url"
printf '%s  %s\n' "$sha" "$temporary" | sha256sum --check -
mv "$temporary" "$destination"
