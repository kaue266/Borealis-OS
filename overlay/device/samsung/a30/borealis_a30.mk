# Android 17 AOSP product for the original A30 partition layout.
$(call inherit-product, $(SRC_TARGET_DIR)/product/product_launched_with_p.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base_telephony.mk)
$(call inherit-product, device/samsung/a30/device.mk)
$(call inherit-product, vendor/borealis/config/common.mk)
PRODUCT_NAME := borealis_a30
PRODUCT_DEVICE := a30
PRODUCT_BRAND := samsung
PRODUCT_MODEL := SM-A305GT
PRODUCT_MANUFACTURER := samsung

# Bound the phone build graph on the 14 GiB development host.
include device/samsung/a30/borealis-analysis-scope.mk
