#!/usr/bin/env bash
# Read: one change directory and its selected hardware recipes. Write: an extracted Android tree.
#
#   android-overlay.sh CHANGES ROOT [NAME=DIR ...]
#
# A change directory holds only declared changes, applied in this order:
#   remove.list   Paths to delete, one per line. Each must exist.
#   install.list  New files: path, mode, uid:gid, SELinux type (- for none), source.
#                 Source ./FILE is in CHANGES; NAME/FILE is FILE in the input NAME=DIR.
#                 Source - makes a directory. To replace a file, remove it first.
#   patches.list  Ordered patches, including selected native recipe fragments.
#   *.patch       Unified diffs (patch -p1); name order when patches.list is absent.
#                 Text before the first --- line explains the change.
# All paths are relative to ROOT. Run under fakeroot so owners, modes and labels survive.
set -euo pipefail
changes=$1 root=$(realpath -e "$2")
shift 2
inputs=("$@")
test -n "${FAKEROOTKEY:-}" || { echo "android-overlay.sh requires fakeroot" >&2; exit 1; }
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

fail() { echo "$changes: $*" >&2; exit 1; }

for listing in remove.list install.list; do
    if [ -f "$changes/$listing" ]; then
        python3 "$(dirname "$0")/../tools/hardware_recipes.py" "$changes/$listing" > "$scratch/$listing"
    fi
done
python3 "$(dirname "$0")/../tools/hardware_recipes.py" --patches "$changes" > "$scratch/patches.list"

# The lines of a list file, without comments and blank lines.
entries() {
    test -f "$scratch/$1" || return 0
    grep -v -e '^#' -e '^[[:space:]]*$' "$scratch/$1" || true
}

# Lists may only name paths inside ROOT.
check_path() {
    case "/$1/" in
        //* | */../* | */./*) fail "not a path inside the partition: $1" ;;
    esac
    local parent
    parent=$(dirname "$root/${1%/}")
    [ "$(realpath -e "$parent")" = "$parent" ] \
        || fail "parent directory is missing or a symlink: $1"
}

# True if the path exists, even as a broken symlink.
exists() { [ -e "$1" ] || [ -L "$1" ]; }

# Sets $from to the file an install.list source names: ./FILE or NAME/FILE.
find_source() {
    local name=${1%%/*} file=${1#*/} input
    from=
    if [ "$name" = . ]; then
        from=$changes/$file
    fi
    for input in "${inputs[@]}"; do
        if [ "${input%%=*}" = "$name" ]; then
            from=${input#*=}/$file
        fi
    done
    test -n "$from" || fail "unknown input $name/ in $1"
    test -f "$from" || fail "missing source $1 ($from)"
}

while read -r path; do
    check_path "$path"
    exists "$root/$path" || fail "cannot remove missing $path"
    rm -r -- "$root/$path"
    echo "$changes: remove $path"
done < <(entries remove.list)

while read -r path mode owner type source; do
    check_path "$path"
    test -n "$source" || fail "install.list needs 5 columns: $path"
    if exists "$root/$path"; then
        fail "$path already exists; remove it first"
    fi
    if [ "$source" = - ]; then
        mkdir -- "$root/$path"
    else
        find_source "$source"
        cp -- "$from" "$root/$path"
    fi
    chmod "$mode" "$root/$path"
    chown "$owner" "$root/$path"
    if [ "$type" != - ]; then
        setfattr -n security.selinux -v "u:object_r:$type:s0" "$root/$path"
    fi
    echo "$changes: install $path"
done < <(entries install.list)

# GNU patch replaces each file it changes, which would drop its owner, mode and SELinux
# label. So patch copies in a scratch directory, then write the results back in place.
while IFS= read -r patch; do
    name=$(basename "$patch")
    copies=$scratch/$name
    files=$(sed -n 's#^+++ b/\([^[:space:]]*\).*#\1#p' "$patch")
    test -n "$files" || fail "$name changes no files"
    for path in $files; do
        check_path "$path"
        [ -f "$root/$path" ] && [ ! -L "$root/$path" ] \
            || fail "$name: $path is not an existing regular file"
        mkdir -p "$(dirname "$copies/$path")"
        cp -- "$root/$path" "$copies/$path"
    done
    # Exact context only; never reverse a patch, keep backups or leave .rej files.
    patch --batch --forward --fuzz=0 --no-backup-if-mismatch --reject-file=- --quiet \
        -p1 -d "$copies" < "$patch" || fail "$name does not apply"
    for path in $files; do
        cat "$copies/$path" > "$root/$path"
    done
    echo "$changes: patch $name"
done < "$scratch/patches.list"
