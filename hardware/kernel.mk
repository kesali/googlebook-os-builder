# Combined-image kernel recipes, in application order after the shared patches.
KERNEL_DRIVER_RECIPES := amdgpu renoir-acp i915
include $(addsuffix /kernel.mk,$(addprefix hardware/drivers/,$(KERNEL_DRIVER_RECIPES)))
