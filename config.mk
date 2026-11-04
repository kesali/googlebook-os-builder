# Build settings. Override any of them on the command line, for example:
#   make unpack RECOVERY_IMAGE=~/Downloads/android-desktop_signed_recovery_image.bin

# Official Googlebook recovery, downloaded separately from editable reference projects.
# About 7.8 GB downloaded, 19 GB unzipped. Another image needs its verified SHA-256 too.
RECOVERY_IMAGE ?= $(RUBY_RECOVERY)
RECOVERY_IMAGE_SHA256 ?= $(RUBY_RECOVERY_SHA)

# Generated files and editable downloaded source. Preserve source edits before deleting.
OUT ?= out

# Name of the Docker image that holds the build tools (docker/Dockerfile).
BUILDER_IMAGE ?= gbos-dali-builder

# Conservative default on this 16 GB laptop. Kbuild remains incremental.
JOBS ?= 4

# Diagnostic image output. `make usb` never writes a physical disk.
USB_IMAGE := $(OUT)/dali-usb.img

# `make deploy USB=/run/media/...` accepts only an already-mounted Dali USB ESP.
USB ?=

# `make qemu`: Android's data partition size (GiB, sparse: uses only what Android writes),
# and the virtual machine's CPUs and memory.
ANDROID_DATA_GIB ?= 32
QEMU_CPUS ?= 4
QEMU_MEMORY ?= 6G
QEMU_VNC_PORT ?= 5900
