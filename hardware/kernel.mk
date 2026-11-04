# Native component fragments from explicitly selected driver recipes, in list order.
HARDWARE_DRIVERS := $(shell sed -e 's/\#.*//' -e '/^[[:space:]]*$$/d' hardware/drivers.list)
HARDWARE_DEVICES := $(shell sed -e 's/\#.*//' -e '/^[[:space:]]*$$/d' hardware/devices.list)
HARDWARE_RECIPES := $(addprefix hardware/drivers/,$(HARDWARE_DRIVERS)) \
	$(addprefix hardware/,$(HARDWARE_DEVICES))
$(foreach recipe,$(HARDWARE_RECIPES),$(if $(wildcard $(recipe)/.),,$(error Missing hardware recipe: $(recipe))))
include $(foreach recipe,$(HARDWARE_RECIPES),$(wildcard $(recipe)/kernel.mk))
include $(foreach recipe,$(HARDWARE_RECIPES),$(wildcard $(recipe)/mesa.mk))
include $(foreach recipe,$(HARDWARE_RECIPES),$(wildcard $(recipe)/minigbm.mk))
