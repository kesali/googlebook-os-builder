# Host make describes the pipeline; all compilation happens in Debian.
include config.mk
include sources.mk

# Keep generated files inside the repository's output area.
ifneq ($(filter $(CURDIR)/out $(CURDIR)/out/%,$(abspath $(OUT))),$(abspath $(OUT)))
$(error OUT must be out or a subdirectory of out)
endif

GOOGLE := $(OUT)/google
DL := $(OUT)/downloads
# Unchanged Project Churro patch from commit 488dab956808916100eca141ee251a5a5773eeba.
# Keep its separate content hash so existing editable kernel trees remain reusable.
EMU_PATCH := kernel/vex-emulate.patch
EMU_SHA := $(shell sha256sum $(EMU_PATCH) | cut -d' ' -f1)
BUSYBOX := $(DL)/busybox-$(BUSYBOX_VERSION)-$(BUSYBOX_SHA)
KERNEL_CACHE := $(OUT)/src/kernel-$(KERNEL_REV)-$(EMU_SHA)
# Our kernel source patches, applied in this order after the emulator patch.
KERNEL_PATCHES := kernel/drm-firmware-handoff.patch kernel/msi-backlight.patch kernel/amdgpu-fast-flips.patch \
	kernel/renoir-capture-buffers.patch kernel/i915-gen4-primary-alpha.patch
KERNEL_PATCH_SHA := $(shell cat $(KERNEL_PATCHES) | sha256sum | cut -d' ' -f1)
KERNEL_SRC := $(KERNEL_CACHE)-$(KERNEL_PATCH_SHA)
DWARVES_SRC := $(OUT)/src/dwarves-$(DWARVES_REV)
GKI_SYMVERS := $(DL)/vmlinux-$(GKI_BUILD)-$(GKI_SYMVERS_SHA).symvers
GKI_ABI_LIST := $(DL)/abi_symbollist-$(GKI_BUILD)-$(GKI_ABI_SHA).raw
GKI_VIRT := $(DL)/virt-initramfs-$(GKI_BUILD)-$(GKI_VIRT_SHA).img
TOOLCHAIN := $(OUT)/toolchain
GKI := $(OUT)/gki
LP_CORE := $(OUT)/src/lp-core-$(LP_CORE_REV)
LP_EXTRAS := $(OUT)/src/lp-extras-$(LP_EXTRAS_REV)
ANDROID := $(OUT)/android
ANDROID_DISK := $(OUT)/android-expanded/disk.img
ANDROID_LAYOUT := android/super-layout.json
MESA := $(OUT)/mesa
MESA_TAR := $(DL)/mesa-$(MESA_SHA).tar.xz
MESA_PATCH := android/mesa-drm-master.patch
MESA_PATCHES := $(MESA_PATCH) android/mesa-radv-two-queues.patch android/mesa-radv-yv12.patch
MESA_SOURCE_SHA := $(shell cat $(MESA_PATCHES) scripts/source.sh | sha256sum | cut -d' ' -f1)
MESA_SRC := $(OUT)/src/mesa-$(MESA_SHA)-$(MESA_SOURCE_SHA)
LIBDRM_TAR := $(DL)/libdrm-$(LIBDRM_SHA).tar.xz
LIBDRM_SRC := $(OUT)/src/libdrm-$(LIBDRM_SHA)
EXPAT_TAR := $(DL)/expat-$(EXPAT_SHA).tar.xz
EXPAT_SRC := $(OUT)/src/expat-$(EXPAT_SHA)
LIBVA_SRC := $(OUT)/src/libva-$(LIBVA_VERSION)-$(LIBVA_REV)
NDK_ZIP := $(DL)/android-ndk-$(NDK_SHA).zip
NDK := $(TOOLCHAIN)/ndk-$(NDK_SHA)
ANDROID_EMU_ZIP := $(DL)/emulator-$(ANDROID_EMU_SHA).zip
ANDROID_EMU := $(OUT)/emulator-$(ANDROID_EMU_SHA)
FIRMWARE_TAR := $(DL)/linux-firmware-$(FIRMWARE_SHA).tar.xz
FIRMWARE := $(OUT)/firmware-$(FIRMWARE_SHA)
MINIGBM := $(OUT)/minigbm
MINIGBM_TAR := $(DL)/minigbm-$(MINIGBM_SHA).tar.gz
MINIGBM_PATCH := android/minigbm-amd.patch
MINIGBM_PATCHES := $(MINIGBM_PATCH) android/minigbm-yuv-pitch.patch
MINIGBM_SOURCE_SHA := $(shell cat $(MINIGBM_PATCHES) scripts/source.sh | sha256sum | cut -d' ' -f1)
MINIGBM_SRC := $(OUT)/src/minigbm-$(MINIGBM_SHA)-$(MINIGBM_SOURCE_SHA)
HEADERS := $(OUT)/android-headers/$(ANDROID_HEADERS_TAG)
CORE_HEADERS := $(OUT)/src/android-core-$(ANDROID_CORE_REV)
LOG_HEADERS := $(OUT)/src/android-logging-$(ANDROID_LOGGING_REV)
HARDWARE_HEADERS := $(OUT)/src/android-hardware-$(ANDROID_HARDWARE_REV)
NATIVE_HEADERS := $(OUT)/src/android-native-$(ANDROID_NATIVE_REV)
DMABUF_HEADERS := $(OUT)/src/android-dmabuf-$(ANDROID_DMABUF_REV)
BASE_HEADERS := $(OUT)/src/android-base-$(ANDROID_BASE_REV)
INTERFACE_HEADERS := $(OUT)/src/android-interfaces-$(ANDROID_INTERFACES_REV)
BUILDTOOLS_ZIP := $(DL)/build-tools-$(ANDROID_BUILDTOOLS_SHA).zip
AIDL := $(TOOLCHAIN)/build-tools-$(ANDROID_BUILDTOOLS_SHA)/aidl
BUILDER := scripts/builder.sh
BUILD_READY := $(OUT)/stamps/builder
export BUILDER_IMAGE JOBS QEMU_VNC_PORT
export SOURCE_DATE_EPOCH := 1790812800
export EXTRA_MOUNTS := $(foreach image,$(wildcard $(RECOVERY_IMAGE)),$(abspath $(image)))

.DEFAULT_GOAL := help
.DELETE_ON_ERROR:
.PHONY: help builder unpack sources kernel initramfs image usb deploy deploy-android shell test smoke toolchain gki laptop-logs lp-tools \
	android-initrd android-disk android-image android-sync android-boot android-uefi-check mesa minigbm minigbm-check qemu qemu-check console update-usb install-usb FORCE

help: ## Show this list
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{ printf "  make %-10s %s\n", $$1, $$2 }'

# Device selection and mounts belong to the host, never a privileged builder container.
update-usb: android-image ## Select an existing Android USB and update OS + boot files, preserving data
	sudo -- python3 tools/update_usb.py "$(ANDROID_DISK)" "$(ANDROID)/boot"

install-usb: android-image ## Select and ERASE a USB with the full Android image; verify read-back
	sudo -- python3 tools/install_usb.py "$(ANDROID_DISK)"

laptop-logs: ## Select an Android USB and read saved boot logs into out/laptop-logs/latest
	python3 tools/laptop_logs.py "$(OUT)/laptop-logs"

builder: $(BUILD_READY) ## Build the Debian tool environment
$(BUILD_READY): docker/Dockerfile
	docker build -t $(BUILDER_IMAGE) docker
	@mkdir -p $(@D) && touch $@

unpack: $(GOOGLE)/inventory.txt ## Inspect Google's read-only recovery image
$(GOOGLE)/inventory.txt: $(RECOVERY_IMAGE) config.mk scripts/unpack.sh \
		tools/lp.py tools/kernel_info.py | $(BUILD_READY)
	$(BUILDER) scripts/unpack.sh $(RECOVERY_IMAGE) $(GOOGLE) $(RECOVERY_IMAGE_SHA256)

# A download's name contains its SHA-256: a new pin is a new file, and a file that exists
# is never checked or fetched again.
$(BUSYBOX): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(BUSYBOX_URL)" "$(BUSYBOX_SHA)" "$@"

# The emulator's bytes select KERNEL_SRC; its timestamp must not recreate that tree.
$(KERNEL_SRC)/.ready: $(KERNEL_PATCHES) | $(EMU_PATCH) $(BUILD_READY)
	$(BUILDER) bash scripts/kernel-source.sh "$(KERNEL_URL)" "$(KERNEL_TAG)" "$(KERNEL_REV)" \
		"$(KERNEL_CACHE)" "$(KERNEL_SRC)" "$(EMU_PATCH)" $(KERNEL_PATCHES)

sources: $(KERNEL_SRC)/.ready ## Fetch the pinned kernel source tree (editable under out/src/)

$(LP_CORE)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh "$(LP_CORE_URL)" "$(LP_CORE_REV)" "$(@D)" fs_mgr/liblp
$(LP_EXTRAS)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh "$(LP_EXTRAS_URL)" "$(LP_EXTRAS_REV)" "$(@D)" partition_tools/lpmake.cc
$(OUT)/lp-tools/lpmake: FORCE $(LP_CORE)/.ready $(LP_EXTRAS)/.ready scripts/lpmake.sh tools/lpmake/CMakeLists.txt $(BUILD_READY)
	$(BUILDER) bash scripts/lpmake.sh "$(LP_CORE)" "$(LP_EXTRAS)" "$(OUT)/lp-tools"
lp-tools: $(OUT)/lp-tools/lpmake ## Build upstream lpmake for disposable super-layout experiments

# FORCE lets the upstream build systems see source edits. Published files keep
# their timestamps when their contents do not change, so downstream steps skip.
kernel: $(OUT)/kernel/bzImage ## Incrementally compile the diagnostic kernel
$(OUT)/kernel/bzImage: FORCE $(KERNEL_SRC)/.ready kernel/msi-diagnostic.config scripts/kernel.sh $(BUILD_READY)
	$(BUILDER) bash scripts/kernel.sh "$(KERNEL_SRC)" "$(OUT)/kernel" kernel/msi-diagnostic.config
# Debian's GRUB as one removable-media EFI file, with boot/loader.cfg built in.
$(OUT)/grub/BOOTX64.EFI: boot/loader.cfg $(BUILD_READY)
	@mkdir -p $(@D)
	$(BUILDER) grub-mkstandalone -O x86_64-efi --locales= --fonts= \
		--modules="part_gpt fat normal linux configfile regexp probe serial test setpci" \
		--output="$@" "boot/grub/grub.cfg=boot/loader.cfg"

$(OUT)/isa-smoke: tools/isa-smoke.c $(BUILD_READY)
	$(BUILDER) gcc -O2 -Wall -Wextra -Werror -static -o "$@" "$<"
initramfs: $(OUT)/initramfs.gz ## Pack BusyBox, boot/init and the CPU self-test
$(OUT)/initramfs.gz: $(BUSYBOX) boot/init $(OUT)/isa-smoke scripts/initramfs.sh
	$(BUILDER) bash scripts/initramfs.sh "$(BUSYBOX)" boot/init "$(OUT)/isa-smoke" "$@"

$(OUT)/boot/manifest.json: $(OUT)/kernel/bzImage $(OUT)/initramfs.gz $(OUT)/grub/BOOTX64.EFI boot/menu.cfg tools/deploy.py
	$(BUILDER) python3 tools/deploy.py bundle --kind diagnostic "$(OUT)/kernel/bzImage" "$(OUT)/initramfs.gz" \
		"$(OUT)/grub/BOOTX64.EFI" boot/menu.cfg "$(OUT)/boot"
image: $(USB_IMAGE) ## Assemble out/dali-usb.img (no root or physical disk writes)
usb: image ## Alias for image; flash it with your preferred USB imaging tool
$(USB_IMAGE): $(OUT)/boot/manifest.json scripts/image.sh tools/deploy.py
	$(BUILDER) bash scripts/image.sh "$(OUT)/boot" "$@"

deploy: $(OUT)/boot/manifest.json ## Update changed boot files: make deploy USB=/mounted/USB
	@test -n "$(USB)" || { echo "Set USB to the mounted DALI-BOOT partition; no raw devices." >&2; exit 1; }
	python3 tools/deploy.py usb "$(OUT)/boot" "$(USB)"

test: $(BUILD_READY) ## Run focused update/safety tests (no physical disks)
	$(BUILDER) python3 -m unittest discover -s tests -v
smoke: image ## UEFI-boot a temporary image in QEMU and test instruction emulation
	$(BUILDER) python3 tools/boot_test.py "$(USB_IMAGE)" "$(OUT)"
shell: $(BUILD_READY) ## Open a shell inside the builder
	$(BUILDER) bash

# Googlebook OS: Google's kernel (GKI) rebuilt from source with Google's compilers.
$(TOOLCHAIN)/clang-$(CLANG_REV)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh "$(CLANG_URL)" "$(CLANG_REV)" "$(@D)" "$(CLANG_DIR)"
$(TOOLCHAIN)/rust-$(RUST_REV)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh "$(RUST_URL)" "$(RUST_REV)" "$(@D)" "$(RUST_DIR)"
$(TOOLCHAIN)/bindgen-$(BINDGEN_REV)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh "$(BINDGEN_URL)" "$(BINDGEN_REV)" "$(@D)" \
		linux-x86/bin/bindgen linux-x86/lib64/libc++.so
$(DWARVES_SRC)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh "$(DWARVES_URL)" "$(DWARVES_REV)" "$(@D)"
$(TOOLCHAIN)/pahole-$(DWARVES_REV)/pahole: $(DWARVES_SRC)/.ready $(KERNEL_SRC)/.ready scripts/pahole.sh
	$(BUILDER) bash scripts/pahole.sh "$(DWARVES_SRC)" "$(KERNEL_SRC)" "$(@D)"

# Stable names for the pinned versions: out/toolchain/{clang,rust,bindgen,pahole}.
toolchain: $(TOOLCHAIN)/.ready ## Fetch Google's kernel compilers (about 7 GB), build pahole
$(TOOLCHAIN)/.ready: $(TOOLCHAIN)/clang-$(CLANG_REV)/.ready $(TOOLCHAIN)/rust-$(RUST_REV)/.ready \
		$(TOOLCHAIN)/bindgen-$(BINDGEN_REV)/.ready $(TOOLCHAIN)/pahole-$(DWARVES_REV)/pahole
	ln -sfn clang-$(CLANG_REV)/$(CLANG_DIR) $(TOOLCHAIN)/clang
	ln -sfn rust-$(RUST_REV)/$(RUST_DIR) $(TOOLCHAIN)/rust
	ln -sfn bindgen-$(BINDGEN_REV)/linux-x86/bin $(TOOLCHAIN)/bindgen
	ln -sfn pahole-$(DWARVES_REV) $(TOOLCHAIN)/pahole
	touch $@

$(GKI_SYMVERS): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(GKI_SYMVERS_URL)" "$(GKI_SYMVERS_SHA)" "$@"
$(GKI_ABI_LIST): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(GKI_ABI_URL)" "$(GKI_ABI_SHA)" "$@"
$(GKI_VIRT): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(GKI_VIRT_URL)" "$(GKI_VIRT_SHA)" "$@"

gki: $(GKI)/bzImage ## Rebuild Google's kernel with the instruction emulator, check kABI
$(GKI)/bzImage: FORCE $(KERNEL_SRC)/.ready $(TOOLCHAIN)/.ready $(GOOGLE)/inventory.txt $(GKI_SYMVERS) $(GKI_ABI_LIST) \
		kernel/gki.config scripts/gki-kernel.sh tools/kernel_certs.py tools/kconfig_check.py tools/kabi_check.py
	$(BUILDER) bash scripts/gki-kernel.sh "$(KERNEL_SRC)" "$(GKI)" "$(TOOLCHAIN)" "$(GOOGLE)/kernel" \
		"$(GKI_SYMVERS)" "$(GKI_ABI_LIST)" kernel/gki.config

$(GKI)/modules/manifest: FORCE $(GKI)/bzImage $(GOOGLE)/inventory.txt scripts/laptop-modules.sh \
		kernel/laptop-modules.list
	$(BUILDER) bash scripts/laptop-modules.sh "$(GKI)/build" "$(TOOLCHAIN)" \
		kernel/laptop-modules.list "$(GOOGLE)" "$(GKI)/modules"

# Android's QEMU userspace: pinned source graphics + unmodified software security HALs.
$(MESA_TAR): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(MESA_URL)" "$(MESA_SHA)" "$@"
$(LIBDRM_TAR): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(LIBDRM_URL)" "$(LIBDRM_SHA)" "$@"
$(EXPAT_TAR): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(EXPAT_URL)" "$(EXPAT_SHA)" "$@"
$(NDK_ZIP): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(NDK_URL)" "$(NDK_SHA)" "$@"
$(ANDROID_EMU_ZIP): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(ANDROID_EMU_URL)" "$(ANDROID_EMU_SHA)" "$@"
$(MESA_SRC)/.ready: $(MESA_TAR) $(MESA_PATCHES) scripts/source.sh
	$(BUILDER) bash scripts/source.sh "$<" "$(@D)" $(MESA_PATCHES)
$(LIBDRM_SRC)/.ready: $(LIBDRM_TAR)
	$(BUILDER) bash scripts/source.sh "$<" "$(@D)"
$(EXPAT_SRC)/.ready: $(EXPAT_TAR)
	$(BUILDER) bash scripts/source.sh "$<" "$(@D)"
$(LIBVA_SRC)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh "$(LIBVA_URL)" "$(LIBVA_REV)" "$(@D)"
$(NDK)/.ready: $(NDK_ZIP) scripts/ndk.sh
	$(BUILDER) bash scripts/ndk.sh "$<" "$(@D)"
$(ANDROID_EMU)/.ready: $(ANDROID_EMU_ZIP) $(GOOGLE)/inventory.txt scripts/emulator.sh tools/lp.py
	$(BUILDER) bash scripts/emulator.sh "$<" "$(GOOGLE)/super" "$(@D)"

$(OUT)/mesa-clc/manifest: FORCE $(MESA_SRC)/.ready scripts/mesa-clc.sh $(BUILD_READY)
	$(BUILDER) bash scripts/mesa-clc.sh "$(MESA_SRC)" "$(OUT)/mesa-clc"
mesa: $(MESA)/manifest ## Incrementally build Mesa softpipe, Iris, Zink, AMD Vulkan and VA-API
$(MESA)/manifest: FORCE $(MESA_SRC)/.ready $(LIBDRM_SRC)/.ready $(EXPAT_SRC)/.ready $(NDK)/.ready $(LIBVA_SRC)/.ready scripts/mesa.sh $(OUT)/mesa-clc/manifest
	$(BUILDER) bash scripts/mesa.sh "$(MESA_SRC)" "$(LIBDRM_SRC)" "$(EXPAT_SRC)" "$(NDK)" "$(MESA)" "$(LIBVA_SRC)" "$(OUT)/mesa-clc"

$(FIRMWARE_TAR): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(FIRMWARE_URL)" "$(FIRMWARE_SHA)" "$@"
$(FIRMWARE)/manifest: $(FIRMWARE_TAR) kernel/msi-firmware.list scripts/firmware.sh
	$(BUILDER) bash scripts/firmware.sh "$<" "$(FIRMWARE_VERSION)" kernel/msi-firmware.list "$(FIRMWARE)"
$(MINIGBM_TAR): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(MINIGBM_URL)" "$(MINIGBM_SHA)" "$@"
$(MINIGBM_SRC)/.ready: $(MINIGBM_TAR) $(MINIGBM_PATCHES) scripts/source.sh
	$(BUILDER) bash scripts/source.sh "$<" "$(@D)" $(MINIGBM_PATCHES)
$(BUILDTOOLS_ZIP): | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(ANDROID_BUILDTOOLS_URL)" "$(ANDROID_BUILDTOOLS_SHA)" "$@"
$(dir $(AIDL))lib64/libc++.so: $(BUILDTOOLS_ZIP)
	@mkdir -p $(@D)
	$(BUILDER) unzip -p "$<" android-37.0/lib64/libc++.so > "$@.partial"
	mv "$@.partial" "$@"
$(AIDL): $(BUILDTOOLS_ZIP) $(dir $(AIDL))lib64/libc++.so
	@mkdir -p $(@D)
	$(BUILDER) unzip -p "$<" android-37.0/aidl > "$@.partial"
	chmod 755 "$@.partial"
	mv "$@.partial" "$@"

# Only headers, at the exact Android release the Google image uses.
$(CORE_HEADERS)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh https://android.googlesource.com/platform/system/core \
		"$(ANDROID_CORE_REV)" "$(@D)" libcutils/include libsystem/include libsync/include
$(LOG_HEADERS)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh https://android.googlesource.com/platform/system/logging \
		"$(ANDROID_LOGGING_REV)" "$(@D)" liblog/include
$(HARDWARE_HEADERS)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh https://android.googlesource.com/platform/hardware/libhardware \
		"$(ANDROID_HARDWARE_REV)" "$(@D)" include_all
$(NATIVE_HEADERS)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh https://android.googlesource.com/platform/frameworks/native \
		"$(ANDROID_NATIVE_REV)" "$(@D)" libs/nativewindow/include libs/nativebase/include \
		libs/arect/include libs/binder/ndk/include_cpp libs/binder/ndk/include_ndk
$(DMABUF_HEADERS)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh https://android.googlesource.com/platform/system/memory/libdmabufheap \
		"$(ANDROID_DMABUF_REV)" "$(@D)" include
$(BASE_HEADERS)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh https://android.googlesource.com/platform/system/libbase \
		"$(ANDROID_BASE_REV)" "$(@D)" include
$(INTERFACE_HEADERS)/.ready: | $(BUILD_READY)
	$(BUILDER) bash scripts/git-fetch.sh https://android.googlesource.com/platform/hardware/interfaces \
		"$(ANDROID_INTERFACES_REV)" "$(@D)" graphics/common/aidl/aidl_api/android.hardware.graphics.common/7 \
		common/aidl/aidl_api/android.hardware.common/2
$(HEADERS)/.ready: $(CORE_HEADERS)/.ready $(LOG_HEADERS)/.ready $(HARDWARE_HEADERS)/.ready \
		$(NATIVE_HEADERS)/.ready $(DMABUF_HEADERS)/.ready $(BASE_HEADERS)/.ready $(INTERFACE_HEADERS)/.ready
	@mkdir -p $(@D)
	ln -sfn "$(abspath $(CORE_HEADERS))" "$(HEADERS)/core"
	ln -sfn "$(abspath $(LOG_HEADERS))" "$(HEADERS)/logging"
	ln -sfn "$(abspath $(HARDWARE_HEADERS))" "$(HEADERS)/hardware"
	ln -sfn "$(abspath $(NATIVE_HEADERS))" "$(HEADERS)/native"
	ln -sfn "$(abspath $(DMABUF_HEADERS))" "$(HEADERS)/dmabuf"
	ln -sfn "$(abspath $(BASE_HEADERS))" "$(HEADERS)/base"
	ln -sfn "$(abspath $(INTERFACE_HEADERS))" "$(HEADERS)/interfaces"
	printf '%s\n' $(ANDROID_CORE_REV) $(ANDROID_LOGGING_REV) $(ANDROID_HARDWARE_REV) \
		$(ANDROID_NATIVE_REV) $(ANDROID_DMABUF_REV) $(ANDROID_BASE_REV) $(ANDROID_INTERFACES_REV) > "$@"

minigbm: $(MINIGBM)/manifest ## Build the Android allocator with AMD Mesa support and ABI checks
minigbm-check: $(MINIGBM_SRC)/.ready $(LIBDRM_SRC)/.ready ## Test allocator buffer handling without a GPU
	$(BUILDER) gcc -std=gnu11 -Wall -Wextra -Werror -Wno-unused-parameter \
		-Itests/gbm -I"$(MINIGBM_SRC)" -I"$(LIBDRM_SRC)/include/drm" \
		tests/gbm-wrapper.c -ldl -o "$(OUT)/gbm-wrapper-test"
	$(BUILDER) "$(OUT)/gbm-wrapper-test"
$(MINIGBM)/manifest: FORCE $(MINIGBM_SRC)/.ready $(HEADERS)/.ready $(NDK)/.ready \
		$(MESA)/manifest $(GOOGLE)/inventory.txt $(AIDL) scripts/minigbm.sh \
		android/minigbm-platform-cxx.h tools/minigbm_abi.py
	$(BUILDER) bash scripts/minigbm.sh "$(MINIGBM_SRC)" "$(HEADERS)" "$(NDK)" "$(MESA)" \
		"$(GOOGLE)" "$(AIDL)" "$(MINIGBM)"

$(ANDROID)/crossystem: android/crossystem-qemu.c $(NDK)/.ready
	@mkdir -p $(@D)
	$(BUILDER) "$(NDK)/toolchains/llvm/prebuilt/linux-x86_64/bin/x86_64-linux-android35-clang" \
		-O2 -Wall -Wextra -Werror -o "$@" "$<"

# Each partition = Google's pristine image + the declared changes in android/<partition>/
# (remove.list, install.list, *.patch; see scripts/android-overlay.sh).
# install.list sources start with one of these names, e.g. emulator/vendor/bin/...
ANDROID_INPUTS := emulator=$(ANDROID_EMU) mesa=$(MESA)/install build=$(ANDROID) \
	minigbm=$(MINIGBM) firmware=$(FIRMWARE) gki=$(GKI)/modules
# $* is the partition name: system, vendor, system_ext or vendor_dlkm.
$(ANDROID)/system_a.img $(ANDROID)/vendor_a.img $(ANDROID)/system_ext_a.img $(ANDROID)/vendor_dlkm_a.img: $(ANDROID)/%_a.img: \
		$(GOOGLE)/inventory.txt scripts/android-partition.sh scripts/android-overlay.sh \
		scripts/check-replacements.sh tools/fs_metadata.py tools/android_layout.py $(ANDROID_LAYOUT)
	$(BUILDER) fakeroot bash scripts/android-partition.sh "$(GOOGLE)" $* android/$* "$@" \
		--layout "$(ANDROID_LAYOUT)" $(ANDROID_INPUTS)

# The directories catch removed files; the wildcards catch edited ones.
$(ANDROID)/system_a.img: android/system $(wildcard android/system/*) $(ANDROID_EMU)/.ready
$(ANDROID)/system_ext_a.img: android/system_ext $(wildcard android/system_ext/*)
$(ANDROID)/vendor_a.img: android/vendor $(wildcard android/vendor/*) scripts/check-vendor-libs.sh \
		$(ANDROID_EMU)/.ready $(MESA)/manifest $(MINIGBM)/manifest $(FIRMWARE)/manifest $(ANDROID)/crossystem
$(ANDROID)/vendor_dlkm_a.img: android/vendor_dlkm $(wildcard android/vendor_dlkm/*) \
		$(GKI)/modules/manifest tools/laptop_module_check.py

$(ANDROID)/vbmeta_a.img: android/bootconfig.txt | $(BUILD_READY)
	@mkdir -p $(@D)
	$(BUILDER) avbtool make_vbmeta_image --algorithm NONE --flags 3 --padding_size 4096 --output "$@"

$(ANDROID)/modules.lz4: $(GOOGLE)/inventory.txt $(GKI_VIRT) scripts/android-modules.sh scripts/android-overlay.sh \
		android/module_ramdisk $(wildcard android/module_ramdisk/*)
	$(BUILDER) fakeroot bash scripts/android-modules.sh "$(GOOGLE)" android/module_ramdisk "$(GKI_VIRT)" "$@"
android-initrd: $(ANDROID)/initrd.img ## Google's ramdisks and QEMU drivers, our boot settings
$(ANDROID)/initrd.img: $(GOOGLE)/inventory.txt $(ANDROID)/modules.lz4 android/bootconfig.txt scripts/android-initrd.sh tools/bootconfig.py
	$(BUILDER) bash scripts/android-initrd.sh "$(GOOGLE)" android/bootconfig.txt "$(ANDROID)/modules.lz4" "$@"

# A new layout uses a new disk path; preserve the old out/android/disk.img as a fallback.
# Once created, this disk holds Android's data and is updated, never regenerated.
android-disk: $(ANDROID_DISK) ## Expanded slot-A layout, empty data, FAT32 boot partition (first build only)
$(ANDROID_DISK): | $(GOOGLE)/inventory.txt $(OUT)/lp-tools/lpmake \
		$(ANDROID)/system_a.img $(ANDROID)/vendor_a.img $(ANDROID)/system_ext_a.img \
		$(ANDROID)/vendor_dlkm_a.img $(ANDROID)/vbmeta_a.img $(ANDROID)/boot/manifest.json
	$(BUILDER) python3 tools/android_fresh.py "$(OUT)/lp-tools/lpmake" "$(RECOVERY_IMAGE)" \
		"$(GOOGLE)" "$(ANDROID)" "$(ANDROID_LAYOUT)" $(ANDROID_DATA_GIB) "$@"

android-sync: $(ANDROID_DISK) $(ANDROID)/system_a.img $(ANDROID)/vendor_a.img $(ANDROID)/system_ext_a.img \
		$(ANDROID)/vendor_dlkm_a.img $(ANDROID)/vbmeta_a.img
	$(BUILDER) python3 tools/android_sync.py "$(ANDROID_DISK)" "$(ANDROID)" --layout "$(ANDROID_LAYOUT)"

# The laptop's boot files: the same kernel and initrd QEMU boots, plus GRUB and its menu.
$(ANDROID)/boot/manifest.json: $(GKI)/bzImage $(ANDROID)/initrd.img $(OUT)/grub/BOOTX64.EFI \
		boot/android-menu.cfg android/cmdline.txt tools/deploy.py
	$(BUILDER) python3 tools/deploy.py bundle --kind android --cmdline android/cmdline.txt "$(GKI)/bzImage" \
		"$(ANDROID)/initrd.img" "$(OUT)/grub/BOOTX64.EFI" boot/android-menu.cfg "$(ANDROID)/boot"
deploy-android: $(ANDROID)/boot/manifest.json ## Update Android boot files: make deploy-android USB=/mounted/USB
	@test -n "$(USB)" || { echo "Set USB to the mounted DALI-BOOT partition; no raw devices." >&2; exit 1; }
	python3 tools/deploy.py usb "$(ANDROID)/boot" "$(USB)"
android-boot: $(ANDROID_DISK) $(ANDROID)/boot/manifest.json ## Put the laptop's boot files into the disk's boot partition
	$(BUILDER) bash scripts/android-boot.sh "$(ANDROID_DISK)" "$(ANDROID)/boot"

android-image: $(GKI)/bzImage $(ANDROID)/initrd.img android-sync android-boot ## Build/update the QEMU image and boot files, preserving Android data

qemu: android-image ## Run Googlebook OS; connect a VNC viewer to localhost:5900
	$(BUILDER) bash scripts/qemu.sh "$(GKI)/bzImage" "$(ANDROID)/initrd.img" "$(ANDROID_DISK)" \
		android/cmdline.txt "$(OUT)/qemu" $(QEMU_CPUS) $(QEMU_MEMORY)

qemu-check: android-image ## Verify full graphical Android startup in a bounded QEMU run
	$(BUILDER) python3 tools/android_smoke.py "$(OUT)" $(QEMU_CPUS) $(QEMU_MEMORY) "$(ANDROID_DISK)"

android-uefi-check: android-image ## Test the laptop boot chain on a temporary USB image with a decoy NVMe
	$(BUILDER) python3 tools/android_uefi_test.py "$(OUT)" $(QEMU_CPUS) $(QEMU_MEMORY) --image "$(ANDROID_DISK)"

console: ## Run a serial-shell command in the running VM: make console COMMAND='getprop'
	python3 tools/android_console.py "$(OUT)/qemu/console.sock" "$(COMMAND)"
