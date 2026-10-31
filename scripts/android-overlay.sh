#!/usr/bin/env bash
# Read: one change directory under android/. Write: those changes into an extracted Android tree.
#
# Usage: android-overlay.sh [--llndk FILE] CHANGES ROOT [NAME=DIR ...]
#
# A change directory holds only declared changes, applied in this order:
#   remove.list   Paths to delete. Each must exist; directories go with their contents.
#   install.list  New files: path, mode, uid:gid, SELinux type (- for none), source.
#                 Source ./FILE is in CHANGES; NAME/FILE is in the input directory NAME=DIR.
#                 A path ending in / is a new directory and takes source -.
#                 To replace a file, remove it first.
#   *.patch       Unified diffs (patch -p1) of existing text files, in name order.
#                 Text before the first --- line explains the change.
# Paths are relative to ROOT and must not leave it. With --llndk, every installed ELF must
# link only to ROOT/lib64 or the platform's LLNDK libraries.
# Run under fakeroot so owners, modes and SELinux labels survive.
set -euo pipefail

llndk=
if [ "${1:-}" = --llndk ]; then
    llndk=$(realpath "$2")
    shift 2
fi
changes=$(realpath "$1") root=$(realpath "$2")
shift 2
fail() { echo "${changes#"$PWD"/}: $*" >&2; exit 1; }
declare -A inputs
for input; do
    [[ $input == ?*=?* ]] || fail "inputs are NAME=DIR, not $input"
    inputs[${input%%=*}]=$(realpath -m "${input#*=}")
done
test -n "${FAKEROOTKEY:-}" || fail "android-overlay.sh requires fakeroot"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

# The entries of a list file, without comments and blank lines.
entries() {
    if [ -f "$changes/$1" ]; then
        grep -v -e '^#' -e '^[[:space:]]*$' "$changes/$1" || true
    fi
}

# ROOT/PATH, refusing paths that could leave ROOT through .. or a symlinked parent.
target() {
    case "/$1/" in
        //* | */../* | */./*) fail "unsafe path: $1" ;;
    esac
    local file=$root/${1%/}
    [ "$(realpath -e "$(dirname "$file")" 2>/dev/null)" = "$(dirname "$file")" ] \
        || fail "parent directory is missing or a symlink: $1"
    printf '%s\n' "$file"
}

# Sets $from_file to the file named by an install.list source.
declare -A used
find_source() {
    local name=${1%%/*} dir
    if [ "$name" = . ]; then
        dir=$changes
        used[${1#./}]=1
    else
        dir=${inputs[$name]:-}
        [ -n "$dir" ] || fail "unknown input $name/ in $1"
    fi
    from_file=$dir/${1#*/}
    [ -f "$from_file" ] || fail "missing source $1 ($from_file)"
}

removed=0
while read -r path extra; do
    [ -z "$extra" ] || fail "remove.list takes one path per line: $path $extra"
    file=$(target "$path")
    [ -e "$file" ] || [ -L "$file" ] || fail "cannot remove missing $path"
    rm -r -- "$file"
    removed=$((removed + 1))
done < <(entries remove.list)

installed=()
while read -r path mode owner type from extra; do
    [ -n "$from" ] && [ -z "$extra" ] || fail "install.list takes 5 columns: $path"
    file=$(target "$path")
    [ ! -e "$file" ] && [ ! -L "$file" ] || fail "$path already exists; remove it first"
    if [ "${path%/}" != "$path" ]; then
        [ "$from" = - ] || fail "directory $path takes source -"
        mkdir -- "$file"
    else
        find_source "$from"
        cp -- "$from_file" "$file"
    fi
    chmod "$mode" "$file"
    chown "$owner" "$file"
    if [ "$type" != - ]; then
        setfattr -n security.selinux -v "u:object_r:$type:s0" "$file"
    fi
    installed+=("$file")
done < <(entries install.list)

patched=0
for patch in "$changes"/*.patch; do
    [ -e "$patch" ] || continue
    name=${patch##*/}
    mapfile -t files < <(sed -n 's#^+++ b/\([^\t]*\).*#\1#p' "$patch")
    [ ${#files[@]} -gt 0 ] || fail "$name changes no files"
    rm -rf "$scratch/tree"
    for path in "${files[@]}"; do
        file=$(target "$path")
        [ -f "$file" ] && [ ! -L "$file" ] || fail "$name: $path is not an existing file"
        mkdir -p "$scratch/tree/$(dirname "$path")"
        cp -- "$file" "$scratch/tree/$path"
    done
    # Patch copies, then write them back in place: GNU patch replaces the files it changes,
    # which would drop their owner, mode and SELinux label.
    patch --batch --forward --fuzz=0 --no-backup-if-mismatch --reject-file=- --quiet \
        -p1 -d "$scratch/tree" -i "$patch" || fail "$name does not apply"
    for path in "${files[@]}"; do
        cat "$scratch/tree/$path" > "$root/$path"
    done
    patched=$((patched + 1))
done

if [ -n "$llndk" ]; then
    for file in "${installed[@]}"; do
        needed=$(readelf -d "$file" 2>/dev/null | sed -n 's/.*(NEEDED).*\[\(.*\)\]$/\1/p') || continue
        for library in $needed; do
            [ -e "$root/lib64/$library" ] || grep -qxF "$library" "$llndk" \
                || fail "${file#"$root"/} needs $library, which is not in lib64 or the LLNDK"
        done
    done
fi

# Every file in a change directory is a declared change.
for file in "$changes"/*; do
    name=${file##*/}
    case "$name" in
        remove.list | install.list | *.patch) ;;
        *) [ -n "${used[$name]:-}" ] || fail "$name is not used by install.list" ;;
    esac
done

echo "${changes##*/}: removed $removed, installed ${#installed[@]}, applied $patched patches"
