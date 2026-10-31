# Host make describes the pipeline; all compilation happens in Debian.
include config.mk
include sources.mk

# Keep generated files inside the repository's output area.
ifneq ($(filter $(CURDIR)/out $(CURDIR)/out/%,$(abspath $(OUT))),$(abspath $(OUT)))
$(error OUT must be out or a subdirectory of out)
endif

GOOGLE := $(OUT)/google
DL := $(OUT)/downloads
EMU_PATCH := $(DL)/emulator-$(EMU_SHA).patch
BUSYBOX_TAR := $(DL)/busybox-$(BUSYBOX_SHA).tar.bz2
GRUB_TAR := $(DL)/grub-$(GRUB_SHA).tar.xz
KERNEL_SRC := $(OUT)/src/kernel-$(KERNEL_REV)-$(EMU_SHA)
BUSYBOX_SRC := $(OUT)/src/busybox-$(BUSYBOX_SHA)
GRUB_SRC := $(OUT)/src/grub-$(GRUB_SHA)
DWARVES_SRC := $(OUT)/src/dwarves-$(DWARVES_REV)
GKI_SYMVERS := $(DL)/vmlinux-$(GKI_BUILD)-$(GKI_SYMVERS_SHA).symvers
TOOLCHAIN := $(OUT)/toolchain
GKI := $(OUT)/gki
BUILDER := scripts/builder.sh
BUILD_READY := $(OUT)/stamps/builder
export BUILDER_IMAGE JOBS
export SOURCE_DATE_EPOCH := 1790812800
export EXTRA_MOUNTS := $(foreach image,$(wildcard $(RECOVERY_IMAGE)),$(abspath $(image)))

.DEFAULT_GOAL := help
.DELETE_ON_ERROR:
.PHONY: help builder unpack sources kernel initramfs image usb deploy shell test smoke toolchain gki FORCE

help: ## Show this list
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{ printf "  make %-10s %s\n", $$1, $$2 }'

builder: $(BUILD_READY) ## Build the Debian tool environment
$(BUILD_READY): docker/Dockerfile
	docker build -t $(BUILDER_IMAGE) docker
	@mkdir -p $(@D) && touch $@

unpack: $(GOOGLE)/inventory.txt ## Inspect Google's read-only recovery image
$(GOOGLE)/inventory.txt: $(RECOVERY_IMAGE) scripts/unpack.sh tools/lp.py tools/kernel_info.py $(BUILD_READY)
	$(BUILDER) scripts/unpack.sh $(RECOVERY_IMAGE) $(GOOGLE)

$(EMU_PATCH): scripts/fetch.sh | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(EMU_URL)" "$(EMU_SHA)" "$@"
$(BUSYBOX_TAR): scripts/fetch.sh | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(BUSYBOX_URL)" "$(BUSYBOX_SHA)" "$@"
$(GRUB_TAR): scripts/fetch.sh | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(GRUB_URL)" "$(GRUB_SHA)" "$@"

$(KERNEL_SRC)/.ready: $(EMU_PATCH) | $(BUILD_READY)
	$(BUILDER) bash scripts/kernel-source.sh "$(KERNEL_URL)" "$(KERNEL_REV)" "$(EMU_PATCH)" "$(KERNEL_SRC)"
$(BUSYBOX_SRC)/.ready: $(BUSYBOX_TAR)
	$(BUILDER) bash scripts/source.sh "$(BUSYBOX_TAR)" "$(BUSYBOX_SRC)"
$(GRUB_SRC)/.ready: $(GRUB_TAR)
	$(BUILDER) bash scripts/source.sh "$(GRUB_TAR)" "$(GRUB_SRC)"

sources: $(KERNEL_SRC)/.ready $(BUSYBOX_SRC)/.ready $(GRUB_SRC)/.ready ## Fetch pinned source trees (editable under out/src/)

# FORCE lets the upstream build systems see source edits. Published files keep
# their timestamps when their contents do not change, so downstream steps skip.
kernel: $(OUT)/kernel/bzImage ## Incrementally compile the diagnostic kernel
$(OUT)/kernel/bzImage: FORCE $(KERNEL_SRC)/.ready kernel/msi-diagnostic.config scripts/kernel.sh $(BUILD_READY)
	$(BUILDER) bash scripts/kernel.sh "$(KERNEL_SRC)" "$(OUT)/kernel" kernel/msi-diagnostic.config
$(OUT)/busybox/busybox: FORCE $(BUSYBOX_SRC)/.ready scripts/busybox.sh $(BUILD_READY)
	$(BUILDER) bash scripts/busybox.sh "$(BUSYBOX_SRC)" "$(OUT)/busybox"
$(OUT)/grub/BOOTX64.EFI: FORCE $(GRUB_SRC)/.ready scripts/grub.sh boot/loader.cfg $(BUILD_READY)
	$(BUILDER) bash scripts/grub.sh "$(GRUB_SRC)" "$(OUT)/grub" "$(abspath boot/loader.cfg)"

$(OUT)/isa-smoke: tools/isa-smoke.c $(BUILD_READY)
	$(BUILDER) gcc -O2 -Wall -Wextra -Werror -static -o "$@" "$<"
initramfs: $(OUT)/initramfs.gz ## Pack BusyBox, boot/init and the CPU self-test
$(OUT)/initramfs.gz: $(OUT)/busybox/busybox boot/init $(OUT)/isa-smoke scripts/initramfs.sh
	$(BUILDER) bash scripts/initramfs.sh "$(OUT)/busybox/busybox" boot/init "$(OUT)/isa-smoke" "$@"

$(OUT)/boot/manifest.json: $(OUT)/kernel/bzImage $(OUT)/initramfs.gz $(OUT)/grub/BOOTX64.EFI boot/menu.cfg tools/deploy.py
	$(BUILDER) python3 tools/deploy.py bundle "$(OUT)/kernel/bzImage" "$(OUT)/initramfs.gz" "$(OUT)/grub/BOOTX64.EFI" boot/menu.cfg "$(OUT)/boot"
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

$(GKI_SYMVERS): scripts/fetch.sh | $(BUILD_READY)
	$(BUILDER) bash scripts/fetch.sh "$(GKI_SYMVERS_URL)" "$(GKI_SYMVERS_SHA)" "$@"

gki: $(GKI)/bzImage ## Rebuild Google's kernel + kernel/gki.config drivers, check kABI
$(GKI)/bzImage: FORCE $(KERNEL_SRC)/.ready $(TOOLCHAIN)/.ready $(GOOGLE)/inventory.txt $(GKI_SYMVERS) \
		kernel/gki.config scripts/gki-kernel.sh tools/kernel_certs.py tools/kconfig_check.py tools/kabi_check.py
	$(BUILDER) bash scripts/gki-kernel.sh "$(KERNEL_SRC)" "$(GKI)" "$(TOOLCHAIN)" "$(GOOGLE)/kernel" \
		"$(GKI_SYMVERS)" kernel/gki.config
