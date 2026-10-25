#!/usr/bin/env python3
"""Check the installed source integration, not physical-device behavior."""
import argparse
import re
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import struct
import json

p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',type=Path);args=p.parse_args()
root=args.source
settings=root/'packages/apps/Settings'
fragment='com.android.settings.borealis.BorealisPerformanceSettings'
assert fragment in (settings/'src/com/android/settings/core/gateway/SettingsGateway.java').read_text()
assert 'class BorealisPerformanceActivity' in (settings/'src/com/android/settings/Settings.java').read_text()
manifest=ET.parse(settings/'AndroidManifest.xml')
ns='{http://schemas.android.com/apk/res/android}'
assert any(a.get(ns+'name')=='Settings$BorealisPerformanceActivity' for a in manifest.findall('.//activity'))
home=ET.parse(settings/'res/xml/top_level_settings.xml')
assert any(a.get(ns+'fragment')==fragment for a in home.getroot())
assert 'BorealisAudioService.class' in (root/'frameworks/base/services/java/com/android/server/SystemServer.java').read_text()
java=(settings/'src/com/android/settings/borealis/BorealisPerformanceSettings.java').read_text()
resources={e.get('name') for f in (settings/'res/values').glob('borealis*.xml') for e in ET.parse(f).getroot()}
java+='\n'+(settings/'src/com/android/settings/borealis/BorealisGraphicsPreferences.java').read_text()
assert set(re.findall(r'R\.string\.(borealis_\w+)',java)) <= resources
for f in (root/'vendor/borealis').rglob('*.xml'):ET.parse(f)
product=(root/'vendor/borealis/config/common.mk').read_text()
assert '    borealis-perf' in product and '    NebulaControl' not in product
assert 'ro.borealis.graphics.fsr=fsr1-experimental' in product
assert 'fonts/BorealisOrbit-Regular.ttf' in product
assert 'ifeq ($(BOREALIS_GRAPHICS_ENABLED),true)' in product
assert 'ro.borealis.graphics.fsr=unavailable' in product
fonts=ET.parse(root/'vendor/borealis/fonts/fonts_customization.xml')
assert any(f.get('name')=='borealis-orbit' and
           f.find('font').text=='BorealisOrbit-Regular.ttf' for f in fonts.getroot())
system_fonts=ET.parse(root/'frameworks/base/data/fonts/fonts.xml')
assert any(f.get('name')=='sans-serif' for f in system_fonts.getroot())
assert (settings/'res/font/borealis_orbit.ttf').read_bytes()==(root/'vendor/borealis/fonts/BorealisOrbit-Regular.ttf').read_bytes()
board=(root/'device/samsung/a30/BoardConfig.mk').read_text()
assert 'BOARD_VENDOR_SEPOLICY_DIRS += vendor/borealis/sepolicy/vendor' in board
assert 'TARGET_PREBUILT_KERNEL := vendor/borealis/prebuilts/kernel/Image' in board
with zipfile.ZipFile(root/'vendor/borealis/media/bootanimation.zip') as z:
    assert z.testzip() is None
    assert all(i.compress_type==zipfile.ZIP_STORED for i in z.infolist())
    assert z.read('desc.txt').splitlines()[0]==b'1080 2340 24'
    frames=[x for x in z.namelist() if x.endswith('.png')]
    assert frames and any(x.startswith('part1/') for x in frames)
    for frame in frames:
        png=z.read(frame)
        assert png[:8]==b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II',png[16:24])==(1080,2340),frame
props='\n'.join(f.read_text() for directory in (
    root/'device/samsung/a30',root/'device/samsung/exynos7885-common',root/'vendor/borealis')
    for f in directory.rglob('*') if f.is_file() and f.suffix in ('.prop','.mk'))
# AOSP 17 defaults this capability to zero; none of the A30 product resources
# may override it to one. Verify the actual default as well as the configuration.
surfaceflinger=(root/'frameworks/native/services/surfaceflinger/SurfaceFlinger.cpp').read_text()
assert 'property_get("ro.surface_flinger.supports_background_blur", value, "0")' in surfaceflinger
assert not re.search(r'ro\.surface_flinger\.supports_background_blur\s*=\s*(?:1|true)\b',props)
assert 'debug.sf.disable_backpressure=1' not in props
service=(root/'vendor/borealis/performance/main.cpp').read_text()
assert 'persist.borealis.perf.cpu_' not in service
# Treble: Settings writes system-owned configuration, and the vendor service
# publishes only vendor-owned status. Keep the property API consistent.
assert '"borealis.perf."' in java and '"persist.borealis.perf."' in java
assert '"vendor.borealis.perf."' in java
assert 'GetProperty("borealis.perf.profile"' in service
assert 'SetProperty("vendor.borealis.perf.status"' in service
assert 'property:borealis.perf.request=*' in (root/'vendor/borealis/performance/borealis-perf.rc').read_text()
assert 'group root system' in (root/'vendor/borealis/performance/borealis-perf.rc').read_text()
assert 'SYSTEM_EXT_PUBLIC_SEPOLICY_DIRS += vendor/borealis/sepolicy/system_ext/public' in board
assert 'system_restricted_prop(borealis_perf_config_prop)' in (root/'vendor/borealis/sepolicy/system_ext/public/property.te').read_text()
assert 'set_prop(system_app, borealis_perf_config_prop)' not in (root/'vendor/borealis/sepolicy/vendor/borealis_perf.te').read_text()
result={'scope':'Android 17 installed source integration; compilation and runtime unverified',
        'passed':True,'checks':['Settings entry/activity and resource references',
        'audio service registration','graphics capability gating',
        'product font with default body font retained','main kernel path',
        '1080x2340 bootanimation header and all frame dimensions',
        'CPU service group','Treble property ownership','Borealis XML parsing'],
        'bootanimation_frames':len(frames),'device_tested':False}
if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
