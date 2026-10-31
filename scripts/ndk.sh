#!/usr/bin/env bash
# Read: verified NDK zip. Write: the Android cross-toolchain, without changing the host.
set -euo pipefail
archive=$1 destination=$2
mkdir -p "$(dirname "$destination")"
work=$(mktemp -d "$destination.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT
unzip -q "$archive" -d "$work"
test -x "$work/android-ndk-r30/toolchains/llvm/prebuilt/linux-x86_64/bin/clang"
test ! -e "$destination"
touch "$work/android-ndk-r30/.ready"
mv "$work/android-ndk-r30" "$destination"
