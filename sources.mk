# Every download: official prebuilts used unchanged, and source we build because we change it
# or no suitable prebuilt exists. Read the release tag or version; the build checks the Git
# commit ID or archive SHA-256 next to it.

# Unchanged official Ruby recovery, matching the existing extracted baseline.
# SHA-256 is for the unzipped image, not its transport ZIP.
RUBY_RECOVERY_BUILD := 16658739
RUBY_RECOVERY_SHA := 805de2e7251b2ec0c2089af0fe8f0547c386a58e8c5e24614d506697456837db
RUBY_RECOVERY_URL := https://dl.google.com/device/recovery/ruby-user/$(RUBY_RECOVERY_BUILD)/recovery.zip
RUBY_RECOVERY_MEMBER := android-desktop_signed_recovery_image.bin

# Google's Android 17 kernel, June 2026 release 52. Built from source because the instruction
# emulator below must be compiled into it. A tag can be moved, so the build also
# checks that it still points at the commit GKI_BUILD (below) was built from.
KERNEL_TAG := android17-6.18-2026-06_r52
KERNEL_REV := 3938c8d97142d5cf31543aa96f864a2cf832dda0
KERNEL_URL := https://android.googlesource.com/kernel/common

# AOSP's lpmake for disposable super-layout experiments. No suitable official standalone
# host prebuilt found. Android 16's liblp format supports this recovery image's metadata;
# commits peeled from android-16.0.0_r1. Build unchanged source with Debian host libraries.
LP_CORE_REV := 68be0c2c0006a0740d0b1809abe4717308f90d15
LP_CORE_URL := https://android.googlesource.com/platform/system/core
LP_EXTRAS_REV := 5578b78e335df1e6d19ddb5bdb26639d383cfdfb
LP_EXTRAS_URL := https://android.googlesource.com/platform/system/extras

# The diagnostic USB's shell: BusyBox's official static binary, unchanged. 1.35.0 is the newest
# one busybox.net publishes, and it has every tool boot/init uses. busybox.net publishes no
# checksum; the SHA-256 was calculated from the HTTPS download.
# The USB's EFI loader is Debian's GRUB (grub-efi-amd64-bin in docker/Dockerfile), also unchanged.
BUSYBOX_VERSION := 1.35.0
BUSYBOX_URL := https://busybox.net/downloads/binaries/$(BUSYBOX_VERSION)-x86_64-linux-musl/busybox
BUSYBOX_SHA := 6e123e7f3202a8c1e9b1f94d8941580a25135382b99e8d3e34fb858bba311348

# Google's own build of KERNEL_TAG, the kernel in the recovery image. Its symbol list
# (CRCs) is what our rebuild must match. The compiler and pahole commits below have no
# release tags; compare them with this build's manifest, which lists every commit used:
# .../$(GKI_BUILD)/kernel_x86_64/latest/raw/manifest_$(GKI_BUILD).xml
GKI_BUILD := 16302624
GKI_SYMVERS_URL := https://ci.android.com/builds/submitted/$(GKI_BUILD)/kernel_x86_64/latest/raw/vmlinux.symvers
GKI_SYMVERS_SHA := db64611c9710f624c60f57219649645d5539c392579a7a8d8d5066b1cc099598
# The exports vendor (unsigned) modules may use. Like Google's build, ours keeps only these
# and what Google's own modules use (CONFIG_TRIM_UNUSED_KSYMS).
GKI_ABI_URL := https://ci.android.com/builds/submitted/$(GKI_BUILD)/kernel_x86_64/latest/raw/abi_symbollist.raw
GKI_ABI_SHA := 75f644ab8d3208d0ee9de45664d831a1721a5a5c283c77dea3cae599884e62ed
# QEMU's virtio drivers (GPU, input, network), prebuilt by Google for this same kernel in its
# virtual-device build. Only the modules listed in android/module_ramdisk/install.list are used.
GKI_VIRT_URL := https://ci.android.com/builds/submitted/$(GKI_BUILD)/kernel_virt_x86_64/latest/raw/initramfs.img
GKI_VIRT_SHA := f827c140e5e20d9cd512e86fac9b22376a26b738af75b3a8b79c3e1f2dcaa9cb

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

# pahole (writes the kernel's BTF type information), built from Google's source. Google's
# kernel build compiles this same commit (Kleaf's pahole_from_sources); the prebuilt in
# kernel/prebuilts/build-tools is an older pahole (1.27).
DWARVES_URL := https://android.googlesource.com/platform/external/dwarves
DWARVES_REV := d884153887ce06fec729061016f7a0b412f08fc6

# QEMU's softpipe fallback and the laptop's RADV/Zink renderer (ACO, no LLVM). Built from
# source: Mesa publishes no Android binaries, and we patch it (android/mesa-drm-master.patch).
MESA_VERSION := 26.3.0-rc3
MESA_URL := https://archive.mesa3d.org/mesa-$(MESA_VERSION).tar.xz
MESA_SHA := 3600c01f11439628d0a85de5ed9cb76f297d13e9783cdeecb91aa685055c9942
LIBDRM_VERSION := 2.4.133
LIBDRM_URL := https://dri.freedesktop.org/libdrm/libdrm-$(LIBDRM_VERSION).tar.xz
LIBDRM_SHA := fc68f9d0ba2ea63c9432a299e14fea09fad7a8a66e8039fcd7802ca59f77b4f5
EXPAT_VERSION := 2.7.3
EXPAT_URL := https://github.com/libexpat/libexpat/releases/download/R_2_7_3/expat-$(EXPAT_VERSION).tar.xz
EXPAT_SHA := 71df8f40706a7bb0a80a5367079ea75d91da4f8c65c58ec59bcdfbf7decdab9f

# libva 2.22.0 (VA-API 1.22), matching Google's camera loader. Only development
# headers are prepared; Google's libva.so stays unchanged. Mesa's AMD VA driver
# has no suitable official Android prebuilt. Commit peeled from upstream tag 2.22.0.
LIBVA_VERSION := 2.22.0
LIBVA_REV := 217da1c28336d6a7e9c0c4cb8f1c303968a675f1
LIBVA_URL := https://github.com/intel/libva.git

# AMD's runtime firmware, unchanged from linux-firmware's official release.
# SHA-256: https://cdn.kernel.org/pub/linux/kernel/firmware/sha256sums.asc
FIRMWARE_VERSION := 20260916
FIRMWARE_URL := https://cdn.kernel.org/pub/linux/kernel/firmware/linux-firmware-$(FIRMWARE_VERSION).tar.xz
FIRMWARE_SHA := f80dcb757a623deda62200c08e0e1a88c76fb6b54964f31b35fa74da1c90ccc5

# LineageOS's upstream minigbm includes its Mesa GBM backend. There is no matching Android
# prebuilt, and Google's allocator lacks AMD support. lineage-23.2's current commit; the
# archive SHA was calculated from this upstream HTTPS URL (the project has no release tags).
MINIGBM_REV := 51b97430ef97474b386bc958d67e5171a86d0d76
MINIGBM_URL := https://codeload.github.com/LineageOS/android_external_minigbm-upstream/tar.gz/$(MINIGBM_REV)
MINIGBM_SHA := e73e16a4d9ae15a49faf299ad14be928bed96004dfb26decd6135d33b75db7f0

# Platform headers for minigbm, not a platform build. These are the peeled commits of
# android-17.0.0_r1 in the named AOSP repositories; git-fetch.sh verifies every file.
ANDROID_HEADERS_TAG := android-17.0.0_r1
ANDROID_CORE_REV := 545d2487e38192a2ce25040897ced877cf6b4f53
ANDROID_LOGGING_REV := d35ba620451b28512f46ebb5421f783fd77968d5
ANDROID_HARDWARE_REV := 97ee3e33ec5ba48c0eca8341ed377ac4497a0678
ANDROID_NATIVE_REV := ae266dcb706d083868578cfedce381ef44488a07
ANDROID_DMABUF_REV := 09fe72b6ce0feead1b97c2859979b125f815d9b0
ANDROID_BASE_REV := fef4173e19d97cd4b4fc09a06bccbf800d0d3937
ANDROID_INTERFACES_REV := 0162af698935100a590b7359581ac8b1b80693e5

# Only the official AIDL compiler is used. SHA-256 calculated after checking Google's
# published SHA-1 (repository2-3.xml): 70954e99f4c3d9d46ee70fa32624672fe7cd6ebe.
ANDROID_BUILDTOOLS_VERSION := 37
ANDROID_BUILDTOOLS_URL := https://dl.google.com/android/repository/build-tools_r$(ANDROID_BUILDTOOLS_VERSION)_linux.zip
ANDROID_BUILDTOOLS_SHA := 01af179347cbcd9c208b7f8171f7b21f6dd1d2f85bcd15e88caa51d5d7b86060

# NDK r30's SHA-256 was calculated after checking Google's published SHA-1:
# 5107f898313790e449e87eee2183d9a20602dee9 (developer.android.com/ndk/downloads).
NDK_URL := https://dl.google.com/android/repository/android-ndk-r30-linux.zip
NDK_SHA := 753611f410d002cfcd3f3dc2ef49aad532089d3180b436c060a90bf0fcb64df2

# Only software KeyMint/Gatekeeper and their missing dependencies are taken from here.
# Google's published SHA-1: 629e507fd5b737c2c836b12b52c81cd0e3b12399.
ANDROID_EMU_URL := https://dl.google.com/android/repository/sys-img/google_apis/x86_64-37.0_r06.zip
ANDROID_EMU_SHA := 43f1d4eadf9117a505bbd815704ac5d9aaf4c7ce61c9d99f66305245ce00a191
