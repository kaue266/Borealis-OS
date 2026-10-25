# BorealisOS Android 17. Google services and app root are absent by default.
BOREALIS_VERSION := 3.0-alpha
PRODUCT_SYSTEM_PROPERTIES += \
    ro.borealis.version=$(BOREALIS_VERSION) \
    ro.borealis.channel=experimental \
    ro.borealis.device=a30 \
    ro.borealis.root=optional \
    ro.borealis.google=none

# Declare capability only after the Android 17 renderer port is integrated.
ifeq ($(BOREALIS_GRAPHICS_ENABLED),true)
PRODUCT_SYSTEM_PROPERTIES += \
    ro.borealis.graphics.fsr=fsr1-experimental \
    ro.borealis.graphics.framegen=optical-flow-experimental
else
PRODUCT_SYSTEM_PROPERTIES += \
    ro.borealis.graphics.fsr=unavailable \
    ro.borealis.graphics.framegen=unavailable
endif

PRODUCT_PACKAGES += \
    BorealisSpace \
    borealis-perf \
    libbundlewrapper \
    Launcher3QuickStep \
    WallpaperPicker2

DEVICE_PACKAGE_OVERLAYS += vendor/borealis/overlay/base
PRODUCT_ENFORCE_RRO_EXCLUDED_OVERLAYS += vendor/borealis/overlay/base

PRODUCT_COPY_FILES += \
    vendor/borealis/prebuilts/kernel/Image:kernel \
    vendor/borealis/fonts/BorealisOrbit-Regular.ttf:$(TARGET_COPY_OUT_PRODUCT)/fonts/BorealisOrbit-Regular.ttf \
    vendor/borealis/fonts/fonts_customization.xml:$(TARGET_COPY_OUT_PRODUCT)/etc/fonts_customization.xml \
    vendor/borealis/media/bootanimation.zip:$(TARGET_COPY_OUT_PRODUCT)/media/bootanimation.zip \
    vendor/borealis/graphics/borealis-graphics.rc:$(TARGET_COPY_OUT_SYSTEM)/etc/init/borealis-graphics.rc

# Keep normal Android process management, thermal limits and scheduling.
# Native vendor service applies validated controls when requested by Settings.
PRODUCT_LOCALES := pt_BR en_US es_US
PRODUCT_BRAND := samsung
PRODUCT_MANUFACTURER := samsung
PRODUCT_MODEL := SM-A305GT
