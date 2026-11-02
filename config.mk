# Build settings. Override any of them on the command line, for example:
#   make unpack RECOVERY_IMAGE=~/Downloads/android-desktop_signed_recovery_image.bin

# Google's official Googlebook recovery image (the unzipped .bin, about 19 GB).
# Only ever read, never modified. If you use another image, set its verified SHA-256 too.
RECOVERY_IMAGE ?= reference/project-churro-msi-modern-15-B7M/android-desktop_signed_recovery_image.bin
RECOVERY_IMAGE_SHA256 ?= 805de2e7251b2ec0c2089af0fe8f0547c386a58e8c5e24614d506697456837db

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
