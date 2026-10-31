# The builder: every tool the build runs, in one place, so the host only needs
# Docker and make. `make builder` rebuilds it whenever this file changes.
FROM debian:trixie-slim

# python3       our tools/*.py, avbtool and unpack_bootimg
# jq            reads the partition table that sfdisk prints as JSON
# fdisk         sfdisk: reads GPT partition tables
# erofs-utils   dump.erofs / fsck.erofs / mkfs.erofs: Android's read-only filesystem
# mkbootimg     unpack_bootimg / mkbootimg: Android boot images
# lz4           unpacks Google's LZ4-compressed kernel
# curl, ca-certificates   download pinned sources
# cmake, libdw-dev        build pahole, which Google's kernel build needs for BTF
# kmod          depmod: writes the module dependency lists
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 jq fdisk erofs-utils mkbootimg lz4 curl ca-certificates \
        build-essential bc bison flex libssl-dev libelf-dev pkg-config \
        git patch xz-utils bzip2 cpio gettext gawk dosfstools mtools \
        qemu-system-x86 ovmf \
        cmake libdw-dev kmod \
    && rm -rf /var/lib/apt/lists/*

# avbtool: reads and writes Android Verified Boot (vbmeta) data. A single
# Python file from AOSP, pinned to a release tag and checked by sha256.
ARG AVB_TAG=android-16.0.0_r1
ARG AVBTOOL_SHA256=e5a664a38db623da00f080219bc0ee60a640a9dc4a872803616fae4938ac749b
RUN curl -fsSL --retry 5 --retry-delay 10 \
        "https://android.googlesource.com/platform/external/avb/+/refs/tags/${AVB_TAG}/avbtool.py?format=TEXT" \
        | base64 -d > /usr/local/bin/avbtool \
    && echo "${AVBTOOL_SHA256}  /usr/local/bin/avbtool" | sha256sum -c - \
    && chmod 755 /usr/local/bin/avbtool

# Android userspace cross-builds and rootless filesystem reconstruction.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        meson ninja-build python3-mako python3-yaml python3-ply python3-packaging \
        unzip e2fsprogs fakeroot attr \
    && rm -rf /var/lib/apt/lists/*
