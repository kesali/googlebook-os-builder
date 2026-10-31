#!/usr/bin/env bash
# Read: Git URL + pinned commit [+ paths]. Write: the files of exactly that commit.
#
#   git-fetch.sh <url> <commit> <destination> [path...]
#
# Without paths, Git downloads the whole commit (fine for source repositories).
#
# With paths, only those directories and files are downloaded. Google's compiler
# repositories hold many multi-GB versions, and Git's on-demand download of large files
# can stall for many minutes, so:
#   1. Git downloads only the commit's file list (names, modes and content hashes).
#   2. The files come from googlesource.com's tarball and file links for the same commit.
#   3. `git status` proves the downloaded files are exactly the commit's files.
set -euo pipefail
url=$1 revision=$2 destination=$3
shift 3
if [ -e "$destination" ]; then
    echo "Refusing to replace $destination" >&2
    exit 1
fi
mkdir -p "$(dirname "$destination")"
temporary=$(mktemp -d "$destination.partial.XXXXXX")
trap 'rm -rf "$temporary"' EXIT
git init --quiet "$temporary"
git -C "$temporary" remote add origin "$url"

if [ $# -eq 0 ]; then
    git -C "$temporary" fetch --depth=1 origin "$revision"
    git -C "$temporary" checkout --quiet --detach FETCH_HEAD
else
    export GIT_NO_LAZY_FETCH=1 # Git must never download file contents itself here
    patterns=()
    for path in "$@"; do patterns+=("/$path"); done
    git -C "$temporary" sparse-checkout set --no-cone "${patterns[@]}"
    git -C "$temporary" fetch --depth=1 --filter=blob:none origin "$revision"
    git -C "$temporary" update-ref --no-deref HEAD FETCH_HEAD
    git -C "$temporary" reset --quiet # file list of the commit, limited to the paths

    for path in "$@"; do
        entry() { git -C "$temporary" ls-tree --format="%($1)" HEAD -- "$path"; }
        case $(entry objecttype) in
        tree)
            # googlesource sometimes cuts long archive downloads off; they can't resume.
            for attempt in 1 2 3; do
                echo "Downloading $path/ (attempt $attempt)"
                rm -rf "${temporary:?}/$path"
                mkdir -p "$temporary/$path"
                if curl -fsSL "$url/+archive/$revision/$path.tar.gz" | tar -xz -C "$temporary/$path"; then
                    break
                fi
                [ "$attempt" -lt 3 ] || exit 1
            done
            ;;
        blob)
            echo "Downloading $path"
            mkdir -p "$(dirname "$temporary/$path")"
            curl -fsSL "$url/+/$revision/$path?format=TEXT" | base64 -d >"$temporary/$path"
            if [ "$(entry objectmode)" = 100755 ]; then chmod +x "$temporary/$path"; fi
            ;;
        *)
            echo "$path is not in $url $revision" >&2
            exit 1
            ;;
        esac
    done

    # Git checks a file by hashing it, but a symlink by reading its stored target: fetch
    # those few tiny entries (in one request) so they can be compared too.
    links=$(git -C "$temporary" ls-files --stage -- "$@" | awk '$1 == 120000 { print $2 }')
    if [ -n "$links" ]; then
        git -C "$temporary" fetch --quiet --no-tags --no-write-fetch-head --filter=blob:none \
            origin --stdin <<<"$links"
    fi
    differences=$(git -C "$temporary" status --porcelain --untracked-files=all)
    if [ -n "$differences" ]; then
        echo "Downloaded files differ from $url $revision:" >&2
        head -n 20 <<<"$differences" >&2
        exit 1
    fi
fi

[ "$(git -C "$temporary" rev-parse HEAD)" = "$revision" ] || {
    echo "Commit verification failed: $url $revision" >&2
    exit 1
}
touch "$temporary/.ready"
mv "$temporary" "$destination"
