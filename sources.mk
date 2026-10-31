# Downloaded source, not executables. Read the release tag or version; the build checks
# the Git commit ID or archive SHA-256 next to it.

# Google's Android 17 kernel, June 2026 release 52. A tag can be moved, so the build also
# checks that it still points at the commit GKI_BUILD (below) was built from.
KERNEL_TAG := android17-6.18-2026-06_r52
KERNEL_REV := 3938c8d97142d5cf31543aa96f864a2cf832dda0
KERNEL_URL := https://android.googlesource.com/kernel/common

# Project Churro's userspace instruction emulator, applied to kernel source.
EMU_REV := 488dab956808916100eca141ee251a5a5773eeba
EMU_URL := https://raw.githubusercontent.com/kesali/project-churro-msi-modern-15-B7M/$(EMU_REV)/kmod/patches/vex-emulate.patch
EMU_SHA := d8decdcffc7a87aea0386ec3ca8476e607f5a26f0ef127e4f051f65ab84e8e0f

BUSYBOX_URL := https://busybox.net/downloads/busybox-1.37.0.tar.bz2
BUSYBOX_SHA := 3311dff32e746499f4df0d5df04d7eb396382d7e108bb9250e7b519b837043a4

GRUB_URL := https://ftp.gnu.org/gnu/grub/grub-2.12.tar.xz
GRUB_SHA := f3c97391f7c4eaa677a78e090c7e97e6dc47b16f655f04683ebd37bef7fe0faa

# Google's own build of KERNEL_TAG, the kernel in the recovery image. Its symbol list
# (CRCs) is what our rebuild must match. The compiler and pahole commits below have no
# release tags; compare them with this build's manifest, which lists every commit used:
# .../$(GKI_BUILD)/kernel_x86_64/latest/raw/manifest_$(GKI_BUILD).xml
GKI_BUILD := 16302624
GKI_SYMVERS_URL := https://ci.android.com/builds/submitted/$(GKI_BUILD)/kernel_x86_64/latest/raw/vmlinux.symvers
GKI_SYMVERS_SHA := db64611c9710f624c60f57219649645d5539c392579a7a8d8d5066b1cc099598

# Google's compilers for that kernel. Each repository holds many versions; we fetch
# only the *_DIR we need. Git verifies the commits.
CLANG_URL := https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86
CLANG_REV := 4a7d0a5e443c27d8f68fbd46abfab464e1355a69
CLANG_DIR := clang-r584948c
RUST_URL := https://android.googlesource.com/platform/prebuilts/rust-toolchain/linux-x86
RUST_REV := a04f70c5179f23eff11c58cb480acee4afb1334b
RUST_DIR := 1.91.1.p3
BINDGEN_URL := https://android.googlesource.com/platform/prebuilts/clang-tools
BINDGEN_REV := 4155cb466dcd9b53c6f873829c53aa6f905449dd

# pahole (writes the kernel's BTF type information), built from Google's source.
DWARVES_URL := https://android.googlesource.com/platform/external/dwarves
DWARVES_REV := d884153887ce06fec729061016f7a0b412f08fc6

# QEMU's software renderer. No LLVM, Vulkan or hardware-specific Mesa drivers yet.
MESA_VERSION := 26.3.0-rc3
MESA_URL := https://archive.mesa3d.org/mesa-$(MESA_VERSION).tar.xz
MESA_SHA := 3600c01f11439628d0a85de5ed9cb76f297d13e9783cdeecb91aa685055c9942
LIBDRM_VERSION := 2.4.133
LIBDRM_URL := https://dri.freedesktop.org/libdrm/libdrm-$(LIBDRM_VERSION).tar.xz
LIBDRM_SHA := fc68f9d0ba2ea63c9432a299e14fea09fad7a8a66e8039fcd7802ca59f77b4f5
EXPAT_VERSION := 2.7.3
EXPAT_URL := https://github.com/libexpat/libexpat/releases/download/R_2_7_3/expat-$(EXPAT_VERSION).tar.xz
EXPAT_SHA := 71df8f40706a7bb0a80a5367079ea75d91da4f8c65c58ec59bcdfbf7decdab9f

# NDK r30's SHA-256 was calculated after checking Google's published SHA-1:
# 5107f898313790e449e87eee2183d9a20602dee9 (developer.android.com/ndk/downloads).
NDK_URL := https://dl.google.com/android/repository/android-ndk-r30-linux.zip
NDK_SHA := 753611f410d002cfcd3f3dc2ef49aad532089d3180b436c060a90bf0fcb64df2

# Only software KeyMint/Gatekeeper and their missing dependencies are taken from here.
# Google's published SHA-1: 629e507fd5b737c2c836b12b52c81cd0e3b12399.
ANDROID_EMU_URL := https://dl.google.com/android/repository/sys-img/google_apis/x86_64-37.0_r06.zip
ANDROID_EMU_SHA := 43f1d4eadf9117a505bbd815704ac5d9aaf4c7ce61c9d99f66305245ce00a191
