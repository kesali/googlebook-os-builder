# Build settings. Override any of them on the command line, for example:
#   make unpack RECOVERY_IMAGE=~/Downloads/android-desktop_signed_recovery_image.bin

# Official Googlebook recovery, downloaded separately from editable reference projects.
# About 7.8 GB downloaded, 19 GB unzipped. Another image needs its verified SHA-256 too.
RECOVERY_IMAGE ?= $(RUBY_RECOVERY)
RECOVERY_IMAGE_SHA256 ?= $(RUBY_RECOVERY_SHA)

# Generated files and editable downloaded source. Preserve source edits before deleting.
OUT ?= out

# Name of the Docker image that holds the build tools (docker/Dockerfile).
BUILDER_IMAGE ?= gbos-builder

# Parallel compile jobs: every CPU by default. Lower it (JOBS=4) if memory runs short.
JOBS ?= $(shell nproc)

# `make qemu`: initial data size (GiB, sparse); fresh USB installation expands it to the device.
# The virtual machine's CPUs and memory follow.
ANDROID_DATA_GIB ?= 32
QEMU_CPUS ?= 4
QEMU_MEMORY ?= 6G
QEMU_VNC_PORT ?= 5900
