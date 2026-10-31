# Downloaded source, not executables. Verify Git commit IDs or archive SHA-256.
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

# Google's own build of KERNEL_REV, the kernel in the recovery image. Its symbol list
# (CRCs) is what our rebuild must match. The toolchain pins below come from this
# build's manifest: .../$(GKI_BUILD)/kernel_x86_64/latest/raw/manifest_$(GKI_BUILD).xml
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
