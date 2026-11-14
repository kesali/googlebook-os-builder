#!/usr/bin/env bash
# Read: URL + SHA-256 + optional ZIP member. Write: one verified source; resume partial downloads.
#
#   fetch.sh <url> <sha256 of published file> <destination> [zip-member]
set -euo pipefail
[ "$#" -eq 3 ] || [ "$#" -eq 4 ] || {
    echo "Usage: fetch.sh URL SHA256 DESTINATION [ZIP_MEMBER]" >&2
    exit 1
}
url=$1 sha=$2 destination=$3
mkdir -p "$(dirname "$destination")"

check_sha() {
    printf '%s  %s\n' "$sha" "$1" | sha256sum --check --status
}

if [ -f "$destination" ] && check_sha "$destination"; then
    exit 0
fi

exec 9>"$destination.fetch.lock"
flock 9
if [ -f "$destination" ] && check_sha "$destination"; then
    exit 0
fi

key=$(printf '%s\0%s\0%s' "$url" "$sha" "${4-}" | sha256sum)
work=$destination.partial.${key%% *}
mkdir -p "$work"
temporary=$work/source
archive=$work/archive.zip
download=$temporary
if [ "$#" -eq 4 ]; then
    download=$archive
fi

if [ "$#" -eq 3 ] && [ -f "$temporary" ] && check_sha "$temporary"; then
    mv "$temporary" "$destination"
    rm -rf "$work"
    exit 0
fi
if [ "$#" -eq 4 ] && [ -f "$archive" ]; then
    if unzip -p "$archive" "$4" > "$temporary" 2>/dev/null && check_sha "$temporary"; then
        mv "$temporary" "$destination"
        rm -rf "$work"
        exit 0
    fi
    rm -f "$temporary"
fi

if curl --fail --location --retry 3 --continue-at - --output "$download" "$url"; then
    :
else
    status=$?
    if [ "$status" -ne 33 ]; then
        if [ ! -s "$download" ]; then
            rm -rf "$work"
        fi
        exit "$status"
    fi
    rm -rf "$work"
    mkdir -p "$work"
    if curl --fail --location --retry 3 --output "$download" "$url"; then
        :
    else
        status=$?
        if [ ! -s "$download" ]; then
            rm -rf "$work"
        fi
        exit "$status"
    fi
fi

if [ "$#" -eq 4 ]; then
    if ! unzip -p "$archive" "$4" > "$temporary"; then
        rm -rf "$work"
        exit 1
    fi
fi
if ! check_sha "$temporary"; then
    echo "SHA-256 mismatch; refusing to publish $destination." >&2
    rm -rf "$work"
    exit 1
fi
mv "$temporary" "$destination"
rm -rf "$work"
