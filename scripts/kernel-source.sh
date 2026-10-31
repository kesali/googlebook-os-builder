#!/usr/bin/env bash
# Read: Android release tag, its expected commit + verified source patch. Write: editable Git checkout.
# Gitiles-generated tarballs need not have stable archive checksums; Git verifies the objects.
set -euo pipefail
url=$1 tag=$2 revision=$3 patch_file=$(realpath "$4") destination=$5
mkdir -p "$(dirname "$destination")"
if [ -e "$destination" ]; then
    echo "Refusing to replace $destination; preserve local source edits first." >&2
    exit 1
fi
temporary=$(mktemp -d "$destination.partial.XXXXXX")
trap 'rm -rf "$temporary"' EXIT
git init --quiet "$temporary"
git -C "$temporary" remote add origin "$url"
git -C "$temporary" fetch --depth=1 origin "refs/tags/$tag"
git -C "$temporary" checkout --quiet --detach FETCH_HEAD
[ "$(git -C "$temporary" rev-parse HEAD)" = "$revision" ] || {
    echo "Tag $tag does not point at the pinned commit $revision" >&2
    exit 1
}
patch --batch --fuzz=0 -d "$temporary" -p1 < "$patch_file"
touch "$temporary/.ready"
mv "$temporary" "$destination"
