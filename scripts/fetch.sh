#!/usr/bin/env bash
# Read: URL + SHA-256 + optional ZIP member. Write: one verified source, never a partial target.
#
#   fetch.sh <url> <sha256 of published file> <destination> [zip-member]
set -euo pipefail
[ "$#" -eq 3 ] || [ "$#" -eq 4 ] || {
    echo "Usage: fetch.sh URL SHA256 DESTINATION [ZIP_MEMBER]" >&2
    exit 1
}
url=$1 sha=$2 destination=$3
mkdir -p "$(dirname "$destination")"
if [ -f "$destination" ] && printf '%s  %s\n' "$sha" "$destination" | sha256sum --check --status; then
    exit 0
fi
work=$(mktemp -d "$destination.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
temporary=$work/source
archive=$work/archive.zip
download=$temporary
if [ "$#" -eq 4 ]; then
    download=$archive
fi
curl --fail --location --retry 3 --output "$download" "$url"
if [ "$#" -eq 4 ]; then
    unzip -p "$archive" "$4" > "$temporary"
fi
printf '%s  %s\n' "$sha" "$temporary" | sha256sum --check -
mv "$temporary" "$destination"
