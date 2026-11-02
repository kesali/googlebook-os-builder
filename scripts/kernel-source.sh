#!/usr/bin/env bash
# Read: Android release tag, expected commit, source patches and an optional existing checkout.
# Write: a new editable Git checkout; never modify the existing checkout.
#
#   kernel-source.sh <url> <tag> <revision> <emulator patch> <handoff patch> <cache> <destination>
# Gitiles-generated tarballs need not have stable archive checksums; Git verifies the objects.
set -euo pipefail
url=$1 tag=$2 revision=$3 emulator_patch=$(realpath "$4") handoff_patch=$(realpath "$5")
cache=$(realpath -m "$6") destination=$7
mkdir -p "$(dirname "$destination")"
if [ -e "$destination" ] || [ -L "$destination" ]; then
    echo "Refusing to replace $destination; preserve local source edits first." >&2
    exit 1
fi
temporary=$(mktemp -d "$destination.partial.XXXXXX")
trap 'rm -rf "$temporary"' EXIT
git init --quiet "$temporary"
git -C "$temporary" remote add origin "$url"
# Reuse committed Git objects, not edits in the existing source checkout. The tag is still
# fetched and checked against the pin below.
if [ -d "$cache/.git" ]; then
    git -C "$cache" cat-file -e "$revision^{commit}" || {
        echo "Cached kernel $cache does not contain $revision" >&2
        exit 1
    }
    git -C "$temporary" fetch --no-tags --depth=1 "$cache" "$revision:refs/cache/kernel"
fi
git -C "$temporary" fetch --depth=1 origin "refs/tags/$tag"
git -C "$temporary" checkout --quiet --detach FETCH_HEAD
[ "$(git -C "$temporary" rev-parse HEAD)" = "$revision" ] || {
    echo "Tag $tag does not point at the pinned commit $revision" >&2
    exit 1
}
git -C "$temporary" update-ref -d refs/cache/kernel
for patch_file in "$emulator_patch" "$handoff_patch"; do
    patch --batch --fuzz=0 -d "$temporary" -p1 < "$patch_file"
done
touch "$temporary/.ready"
# Another build may create the destination while this checkout is prepared.
mv --no-clobber --no-target-directory "$temporary" "$destination"
if [ -e "$temporary" ]; then
    echo "Refusing to replace $destination; preserve local source edits first." >&2
    exit 1
fi
