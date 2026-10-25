#
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

ifneq ($(filter exynos7884B exynos7904,$(TARGET_SOC)),)
ifdef BOARD_PREBUILT_DTBIMAGE
# The inspected A30 DTB is installed by releasetools/Android.mk's add-radio-file.
# Keep a single producer; do not build from the unused legacy KERNEL_OBJ tree.
INSTALLED_DTBIMAGE_TARGET := $(PRODUCT_OUT)/dtb.img
else
MKDTBOIMG  := $(HOST_OUT_EXECUTABLES)/mkdtboimg$(HOST_EXECUTABLE_SUFFIX)
KERNEL_OUT := $(TARGET_OUT_INTERMEDIATES)/KERNEL_OBJ
DTB_DIR    := $(KERNEL_OUT)/arch/$(KERNEL_ARCH)/boot/dts/exynos
DTB_CFG    := $(COMMON_PATH)/configs/kernel/exynos7885.cfg

INSTALLED_DTBIMAGE_TARGET := $(PRODUCT_OUT)/dtb.img

$(INSTALLED_DTBIMAGE_TARGET): $(PRODUCT_OUT)/kernel $(MKDTBOIMG)
	$(hide) echo "Building dtb.img"
	$(hide) $(MKDTBOIMG) cfg_create $@ $(DTB_CFG) -d $(DTB_DIR)
	$(hide) $(call assert-max-image-size,$@,$(BOARD_DTBIMG_PARTITION_SIZE),raw)

endif # BOARD_PREBUILT_DTBIMAGE

.PHONY: dtbimage
dtbimage: $(INSTALLED_DTBIMAGE_TARGET)

INSTALLED_RADIOIMAGE_TARGET += $(INSTALLED_DTBIMAGE_TARGET)
endif
