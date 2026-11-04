#!/usr/bin/env bash
# Read: Google's pristine EROFS partition, its change directory and the changed partition tree.
# Check: every file listed in both remove.list and install.list (a replacement of one of Google's
# files) is a drop-in replacement. An ELF file must still export every dynamic symbol of Google's
# file that a program in the partition imports, or that program fails to load. Prebuilt donors
# should export all of them; our source builds may lack internal helpers nothing imports.
# An APEX must have Google's manifest (name and version) and file list. Its public files, which
# the partition shows as symlinks into /apex/NAME/, must export everything Google's did: programs
# on every partition link to them. Its other files are private to the APEX's own build.
#
#   check-replacements.sh GOOGLE_PARTITION CHANGES ROOT
set -euo pipefail
export LC_ALL=C  # comm needs one sort order
google=$(realpath "$1") changes=$2 root=$(realpath "$3")
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

for listing in remove.list install.list; do
    if [ -f "$changes/$listing" ]; then
        python3 "$(dirname "$0")/../tools/hardware_recipes.py" "$changes/$listing" > "$scratch/$listing"
    fi
done

entries() {
    test -f "$scratch/$1" || return 0
    grep -v -e '^#' -e '^[[:space:]]*$' "$scratch/$1" | awk '{print $1}' || true
}

is_elf() { cmp -s -n 4 "$1" <(printf '\177ELF'); }

# Defined dynamic symbols with their versions, e.g. malloc@@LIBC.
exports() {
    readelf --dyn-syms --wide "$1" | awk '$1 ~ /^[0-9]+:$/ && $5 != "LOCAL" && $7 != "UND" {print $8}' \
        | sort -u
}

# Names of the symbols that ELF files in the partition import, computed once (it reads every file).
imports() {
    if [ ! -f "$scratch/imports" ]; then
        find "$root" -type f -size +0 -print0 \
            | xargs -0 readelf --dyn-syms --wide 2> /dev/null \
            | awk '$1 ~ /^[0-9]+:$/ && $7 == "UND" && $8 != "" {sub(/@.*/, "", $8); print $8}' \
            | sort -u > "$scratch/imports" || true
    fi
    cat "$scratch/imports"
}

# check_elf NAME GOOGLE_FILE REPLACEMENT [every-export]
check_elf() {
    local name=$1 original=$2 replacement=$3 scope=${4:-imported} missing
    is_elf "$replacement" || { echo "$name: replacement is not an ELF file" >&2; exit 1; }
    missing=$(comm -23 <(exports "$original") <(exports "$replacement") | sed 's/@.*//' | sort -u)
    if [ -n "$missing" ] && [ "$scope" = imported ]; then
        missing=$(comm -12 <(echo "$missing") <(imports))
    fi
    if [ -n "$missing" ]; then
        echo "$name: replacement lacks exports of Google's file ($scope):" >&2
        echo "$missing" | head -20 >&2
        exit 1
    fi
}

# Extracts an APEX's payload filesystem (EROFS in Google's builds, ext4 in some others).
apex_payload() {
    local apex=$1 directory=$2
    unzip -p "$apex" apex_payload.img > "$scratch/payload.img"
    if dump.erofs "$scratch/payload.img" > /dev/null 2>&1; then
        fsck.erofs --extract="$directory" "$scratch/payload.img" > /dev/null
    else
        mkdir "$directory"
        debugfs -R "rdump / $directory" "$scratch/payload.img" > /dev/null 2>&1
    fi
    rm "$scratch/payload.img"
}

check_apex() {
    local name=$1 original=$2 replacement=$3 apex public file
    cmp -s <(unzip -p "$original" apex_manifest.pb) <(unzip -p "$replacement" apex_manifest.pb) || {
        echo "$name: replacement APEX has a different name or version" >&2
        exit 1
    }
    rm -rf "$scratch/google-apex" "$scratch/new-apex"
    apex_payload "$original" "$scratch/google-apex"
    apex_payload "$replacement" "$scratch/new-apex"
    diff <(cd "$scratch/google-apex" && find . ! -type d ! -path './lost+found/*' | sort) \
         <(cd "$scratch/new-apex" && find . ! -type d ! -path './lost+found/*' | sort) >&2 || {
        echo "$name: replacement APEX has a different file list" >&2
        exit 1
    }
    # For example system/lib64/libc.so -> /apex/com.android.runtime/lib64/bionic/libc.so.
    apex=/apex/$(basename "$name" .apex)
    public=$(find "$root" -type l -lname "$apex/*" -printf '%l\n' | sed "s|^$apex/|./|" | sort -u)
    test -n "$public" || {
        echo "$name: no symlink into $apex shows which of its files are public" >&2
        exit 1
    }
    for file in $public; do
        check_elf "$name:$file" "$scratch/google-apex/$file" "$scratch/new-apex/$file" every-export
    done
}

for path in $(comm -12 <(entries remove.list | sort) <(entries install.list | sort)); do
    dump.erofs --path="/$path" --cat "$google" > "$scratch/original"
    if [[ "$path" == *.apex ]]; then
        check_apex "$path" "$scratch/original" "$root/$path"
    elif is_elf "$scratch/original"; then
        check_elf "$path" "$scratch/original" "$root/$path"
    fi
    echo "$changes: $path is a drop-in replacement"
done
