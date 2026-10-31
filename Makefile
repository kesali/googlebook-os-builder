# gbos-dali: a Googlebook OS USB stick for the MSI Modern 15 B7M, built from
# Google's recovery image plus our own source-built parts.
#
# Run `make` (or `make help`) for the list of targets. Settings: config.mk.
# Each target names the files it needs, so `make` only redoes steps whose
# inputs changed.

include config.mk

# Pristine pieces unpacked from the recovery image; every later step reads these.
GOOGLE := $(OUT)/google

# Every tool runs inside the builder container (scripts/builder.sh). The
# recovery image is mounted read-only in case it lives outside the repository.
BUILDER := scripts/builder.sh
export BUILDER_IMAGE
export EXTRA_MOUNTS := $(abspath $(RECOVERY_IMAGE))

.DEFAULT_GOAL := help
.PHONY: help builder unpack shell clean

help: ## Show this list
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{ printf "  make %-8s %s\n", $$1, $$2 }'

builder: $(OUT)/stamps/builder ## Build the Docker image with all build tools
$(OUT)/stamps/builder: docker/Dockerfile
	docker build -t $(BUILDER_IMAGE) docker
	@mkdir -p $(@D) && touch $@

unpack: $(GOOGLE)/inventory.txt ## Unpack the recovery image into out/google/
$(GOOGLE)/inventory.txt: $(RECOVERY_IMAGE) scripts/unpack.sh tools/lp.py tools/kernel_info.py $(OUT)/stamps/builder
	$(BUILDER) scripts/unpack.sh $(RECOVERY_IMAGE) $(GOOGLE)

shell: $(OUT)/stamps/builder ## Open a shell inside the builder container
	$(BUILDER) bash

clean: ## Delete out/ (the recovery image is never touched)
	rm -rf $(OUT)
