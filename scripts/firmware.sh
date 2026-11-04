#!/usr/bin/env bash
# Read: pinned linux-firmware archive and a list of filenames. Write: unchanged runtime blobs.
#
#   firmware.sh <archive> <release> <list> <output>
set -euo pipefail
archive=$(realpath "$1") release=$2 list=$(realpath "$3") output=$(realpath -m "$4")
mkdir -p "$(dirname "$output")"
work=$(mktemp -d "$output.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir "$work/files"
python3 "$(dirname "$0")/../tools/hardware_recipes.py" "$list" > "$work/firmware.list"
while read -r path; do
    [[ -z "$path" || "$path" == \#* ]] && continue
    [[ ( "$path" == amdgpu/*.bin || "$path" == mediatek/*.bin ) && "$path" != *..* ]] || {
        echo "Invalid runtime firmware path: $path" >&2; exit 1;
    }
    printf 'linux-firmware-%s/%s\n' "$release" "$path" >> "$work/members"
done < "$work/firmware.list"
tar -xf "$archive" --strip-components=1 -C "$work/files" -T "$work/members"
while read -r path; do
    [[ -z "$path" || "$path" == \#* ]] && continue
    test -s "$work/files/$path"
    mkdir -p "$output/$(dirname "$path")"
    if ! cmp -s "$work/files/$path" "$output/$path"; then
        cp -L "$work/files/$path" "$output/$path.partial"
        mv "$output/$path.partial" "$output/$path"
    fi
    (cd "$output" && sha256sum "$path") >> "$work/manifest"
done < "$work/firmware.list"
test -s "$work/manifest"
if ! cmp -s "$work/manifest" "$output/manifest"; then
    mv "$work/manifest" "$output/manifest"
fi
