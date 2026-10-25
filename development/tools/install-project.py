#!/usr/bin/env python3
"""Install the Android 17 A30 bring-up and Borealis native controls.

Source changes are saved as reviewable patches. This tool never flashes a phone.
"""
from pathlib import Path
import difflib
import json
import re
import shutil
import subprocess

package=Path(__file__).resolve().parent.parent
root=Path('/home/android/borealisos-android17')
assert (root/'device/samsung/a30/device.mk').is_file()
assert (root/'build/release/release_configs/cp2a.textproto').is_file()
proof=package/'validation/port';proof.mkdir(parents=True,exist_ok=True)
changes=[]

def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not path.is_file() or path.read_bytes()!=data:path.write_bytes(data)

for item in (package/'project').rglob('*'):
 if item.is_file():write(root/item.relative_to(package/'project'),item.read_bytes())

def edit(name,transform):
 file=root/name;before=file.read_text();after=transform(before)
 if before!=after:file.write_text(after)
 changes.append(name)
 try:
  original=subprocess.check_output(['git','show','HEAD:'+str(file.relative_to(Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=file.parent,text=True).strip())))],cwd=file.parent,text=True)
 except subprocess.CalledProcessError:original=before
 (proof/(name.replace('/','__')+'.patch')).write_text(''.join(difflib.unified_diff(original.splitlines(True),after.splitlines(True),fromfile='a/'+name,tofile='b/'+name)))

def once(text,anchor,extra):
 if extra.strip() in text:return text
 assert text.count(anchor)==1,f'Changed Android 17 integration anchor: {anchor}'
 return text.replace(anchor,anchor+extra,1)

def device(text):
 text=text.replace('TARGET_SCREEN_HEIGHT := 2280','TARGET_SCREEN_HEIGHT := 2340')
 # The public reference does not provide these optional FM sources.
 return re.sub(r'# FM radio\nPRODUCT_PACKAGES \+= \\\n    S5E7885FMRadio \\\n    miku.dayo.hardware.fmradio-service\n',
  '# FM radio omitted from this alpha: public FM HAL source unavailable.\n',text)
edit('device/samsung/a30/device.mk',device)
extra='''
# Borealis Android 17 bring-up: public R24U artifacts, root optional.
TARGET_PREBUILT_KERNEL := vendor/borealis/prebuilts/kernel/Image
TARGET_NO_KERNEL := false
BOARD_BOOT_HEADER_VERSION := $(BOARD_BOOTIMG_HEADER_VERSION)
BOARD_PREBUILT_DTBOIMAGE := vendor/borealis/prebuilts/kernel/dtbo.img
BOARD_PREBUILT_DTBIMAGE := vendor/borealis/prebuilts/kernel/dtb.img
TARGET_OTA_ASSERT_DEVICE := a30,a30dd,a30xx
BOARD_VENDOR_SEPOLICY_DIRS += vendor/borealis/sepolicy/vendor
SYSTEM_EXT_PUBLIC_SEPOLICY_DIRS += vendor/borealis/sepolicy/system_ext/public
SYSTEM_EXT_PRIVATE_SEPOLICY_DIRS += vendor/borealis/sepolicy/system_ext/private
'''
edit('device/samsung/a30/BoardConfig.mk',lambda s:s.split('# Borealis Android 17 bring-up:',1)[0].rstrip()+'\n'+extra)

def common(text):
 text=text.replace('# GMS\nTARGET_USES_MINI_GAPPS := true','# Borealis does not include Google services.')
 text=text.replace('    $(LOCAL_PATH)/overlay \\\n    $(LOCAL_PATH)/overlay-lineage','    $(LOCAL_PATH)/overlay')
 # AOSP handles ordinary storage; this tree's kernel does not advertise casefold.
 text=text.replace('$(call inherit-product, $(SRC_TARGET_DIR)/product/emulated_storage.mk)',
                   '# Keep AOSP storage defaults; do not require unimplemented casefold support.')
 return text
edit('device/samsung/exynos7885-common/exynos7885-common.mk',common)

# Unselected Lineage frontends still participate in Soong dependency analysis.
# Their APIs do not exist in AOSP; the Borealis native Settings provides controls.
for application in ('AdvancedDisplay','Doze'):
 edit('hardware/samsung/packages/'+application+'/Android.bp',lambda text:
  '// Borealis AOSP: Lineage-only optional frontend excluded from this product.\n')

# Vendor blobs link Samsung's actual TEE library; add its explicit namespace.
for name in ('vendor/samsung/a30/Android.bp','vendor/samsung/exynos7885-common/Android.bp'):
 edit(name,lambda text:text if '"hardware/samsung",' in text else
  text.replace('imports: [','imports: [\n        "hardware/samsung",',1))

# This legacy Exynos dumpstate provider is not selected by the A30 product.
# Android 17 supplies its own dumpstate, and removed this old HIDL interface.
edit('hardware/samsung_slsi-linaro/exynos/dumpstate/Android.bp',lambda text:
 '// Borealis A30 uses AOSP dumpstate; unselected legacy HIDL provider excluded.\n')

# The Exynos7904 product selects Samsung's Teegris Keymaster 4 HAL, not SSP.
# Unselected SSP VTS targets mix KeyMint 4 with Android 17's KeyMint 5 support.
for blueprint in (root/'hardware/samsung_slsi-linaro/exynos/ssp').rglob('Android.bp'):
 edit(str(blueprint.relative_to(root)),lambda text:
  '// Borealis A30 has no SSP/StrongBox provider; keep its selected Teegris Keymaster HAL.\n')

# Android 17's battery monitor and health translation library use Health AIDL 5.
# Compile the selected Pixel helpers against that same generated interface.
edit('hardware/google/pixel/health/Android.bp',lambda text:
 text.replace('android.hardware.health-V4-ndk','android.hardware.health-V5-ndk'))

fragment='com.android.settings.borealis.BorealisPerformanceSettings'
edit('packages/apps/Settings/src/com/android/settings/Settings.java',lambda s:s if 'class BorealisPerformanceActivity' in s else s[:s.rfind('}')]+\
 '    public static class BorealisPerformanceActivity extends SettingsActivity {}\n'+s[s.rfind('}'):])
edit('packages/apps/Settings/src/com/android/settings/core/gateway/SettingsGateway.java',lambda s:once(s,'ENTRY_FRAGMENTS = {','\n        "'+fragment+'",'))
entry='''    <com.android.settings.widget.HomepagePreference
        android:fragment="com.android.settings.borealis.BorealisPerformanceSettings"
        android:icon="@drawable/ic_borealis" android:key="top_level_borealis"
        android:order="-115" android:title="@string/borealis_title"
        android:summary="@string/borealis_summary" />
'''
edit('packages/apps/Settings/res/xml/top_level_settings.xml',lambda s:s if 'top_level_borealis' in s else s.replace('</PreferenceScreen>',entry+'\n</PreferenceScreen>',1))
activity='''        <activity android:name="Settings$BorealisPerformanceActivity"
            android:label="@string/borealis_title" android:exported="true">
            <intent-filter><action android:name="org.borealis.settings.PERFORMANCE" />
                <category android:name="android.intent.category.DEFAULT" /></intent-filter>
            <meta-data android:name="com.android.settings.FRAGMENT_CLASS"
                android:value="com.android.settings.borealis.BorealisPerformanceSettings" />
        </activity>
'''
edit('packages/apps/Settings/AndroidManifest.xml',lambda s:s if 'Settings$BorealisPerformanceActivity' in s else s.replace('</application>',activity+'\n    </application>',1))
edit('frameworks/base/services/java/com/android/server/SystemServer.java',lambda s:once(s,
 'mSystemServiceManager.startService(AudioService.Lifecycle.class);',
 '\n                mSystemServiceManager.startService(com.android.server.borealis.BorealisAudioService.class);'))

# AOSP has no Lineage vendor_init hook. Link only the A30 model/NFC detection.
def init_bp(text):
 if '// Borealis A30 model/SKU hook.' in text:return text
 anchor='    name: "libinit",'
 assert text.count(anchor)==1
 return text.replace(anchor,anchor+'\n    // Borealis A30 model/SKU hook.\n    whole_static_libs: ["//device/samsung/exynos7885-common:libinit_exynos7885"],',1)
edit('system/core/init/Android.bp',init_bp)
def init_properties(text):
 if '// Borealis A30 model/SKU hook.' in text:return text
 text=once(text,'#include "util.h"','\n\nextern void vendor_load_properties(void);')
 anchor='    property_initialize_ro_product_props();'
 assert text.count(anchor)==1
 return text.replace(anchor,'    // Borealis A30 model/SKU hook.\n    vendor_load_properties();\n'+anchor,1)
edit('system/core/init/property_service.cpp',init_properties)
def samsung_init(text):
 text=text.replace('#include "vendor_init.h"','#include <cstring>')
 if 'if (model.empty()) model = GetProperty' not in text:
  text=text.replace('  bool isNFC = false;','  if (model.empty()) model = GetProperty("ro.product.model", "SM-A305GT");\n  bool isNFC = false;',1)
 return text
edit('device/samsung/exynos7885-common/init/init_exynos7885.cpp',samsung_init)

# Only forward build resource knobs, because Soong sanitizes its process env.
def memory_soong(text):
 if '// Borealis build host memory bounds.' in text:return text
 return once(text,'\tinvocationEnv := make(map[string]string)','''
	// Borealis build host memory bounds.
	for _, key := range []string{"GOGC", "GOMAXPROCS", "GOMEMLIMIT"} {
		if value, ok := config.Environment().Get(key); ok && value != "" {
			invocationEnv[key] = value
		}
	}
''')
edit('build/soong/ui/build/soong.go',memory_soong)
edit('build/blueprint/bootstrap/command.go',lambda text:text if '// Borealis build CPU bound.' in text else
 text.replace('\truntime.GOMAXPROCS(runtime.NumCPU())','\t// Borealis build CPU bound.\n\tif os.Getenv("GOMAXPROCS") == "" {\n\t\truntime.GOMAXPROCS(runtime.NumCPU())\n\t}',1))

# DTB and DTBO retain the original A30/AOSP enforcing upstream profile 9.
write(root/'device/samsung/exynos7885-common/releasetools/Android.mk',b'''LOCAL_PATH := $(call my-dir)
$(call add-radio-file,dtb.img)
''')
# add-radio-file resolves its input relative to LOCAL_PATH.
dtb=package/'project/vendor/borealis/prebuilts/kernel/dtb.img'
if dtb.is_file():write(root/'device/samsung/exynos7885-common/releasetools/dtb.img',dtb.read_bytes())
write(root/'device/samsung/exynos7885-common/releasetools/releasetools.py',b'''# SPDX-License-Identifier: Apache-2.0
import common

def FullOTA_InstallEnd(info):
    for directory, name in (("RADIO", "dtb.img"), ("IMAGES", "dtbo.img")):
        data = info.input_zip.read(directory + "/" + name)
        common.ZipWriteStr(info.output_zip, name, data)
        partition = name.removesuffix(".img")
        info.script.AppendExtra('package_extract_file("%s", "/dev/block/by-name/%s");' % (name, partition))

def IncrementalOTA_InstallEnd(info):
    raise RuntimeError("Borealis alpha requires a full OTA; device migration unverified")
''')

(proof/'integration.json').write_text(json.dumps({'source':'android17-release','sdk':37,
 'changed_files':changes,'google_services':False,'root':'optional',
 'device_boot_tested':False,'graphics_renderer_port':'pending; capability remains unavailable',
 'optional_omissions':['FM radio: public HAL source unavailable']},indent=2)+'\n')
print('Installed Android 17 Borealis product, controls and native resource overlays. Build validation pending.')
