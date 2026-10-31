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
