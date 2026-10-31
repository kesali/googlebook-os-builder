# Build settings. Override any of them on the command line, for example:
#   make unpack RECOVERY_IMAGE=~/Downloads/android-desktop_signed_recovery_image.bin

# Google's official Googlebook recovery image (the unzipped .bin, about 19 GB).
# Only ever read, never modified. Where to get it: README.md, "Input".
RECOVERY_IMAGE ?= reference/project-churro-msi-modern-15-B7M/android-desktop_signed_recovery_image.bin

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
