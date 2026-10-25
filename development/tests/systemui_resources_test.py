#!/usr/bin/env python3
"""Verify the power/volume resource contract against the actual AOSP checkout."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET

package = Path(__file__).resolve().parent.parent
root = Path('/home/android/borealisos-android17')
base = root / 'frameworks/base/packages/SystemUI/res'
relative = Path('vendor/borealis/overlay/base/frameworks/base/packages/SystemUI/res')
overlay = package / 'project' / relative
a = lambda name: '{http://schemas.android.com/apk/res/android}' + name
proof = json.loads((package / 'validation/systemui-layouts.json').read_text())
checks = []


def ids(tree):
    return [(node.get(a('id')), node.tag) for node in tree.iter() if node.get(a('id'))]


for resource in proof['resources']:
    name = resource['resource']
    before = ET.parse(base / name).getroot()
    after = ET.parse(overlay / name).getroot()
    assert ids(before) == ids(after), name + ': native binding mismatch'
    assert before.tag == after.tag, name + ': incompatible drawable/view root'
    if 'Licensed under the Apache License' in (base / name).read_text():
        assert 'Licensed under the Apache License' in (overlay / name).read_text()
    for node in after.iter():
        assert node.get(a('importantForAccessibility')) != 'no'
        assert node.get(a('contentDescription')) != '@null'
    checks.append(name + ': native contract and accessibility retained')

for name in ('global_actions_grid_item_lite.xml', 'global_actions_grid_item_v2.xml'):
    tree = ET.parse(overlay / 'layout' / name).getroot()
    assert tree.get(a('layout_height')) == 'wrap_content', 'Font growth is clipped'
    assert tree.get(a('stateListAnimator')) == ET.parse(base / 'layout' / name).getroot().get(a('stateListAnimator'))
    label = next(node for node in tree.iter() if node.get(a('id')) == '@*android:id/message')
    assert label.get(a('singleLine')) != 'true', 'Translated labels must wrap'
    assert label.get(a('maxLines')) == '2'
checks.append('Power actions retain native animation and allow two-line translated labels')

dimens = {node.get('name'): node.text for node in ET.parse(overlay / 'values/borealis_dimens.xml').getroot()}
native_dimens = {node.get('name'): node.text for node in ET.parse(base / 'values/dimens.xml').getroot()}
for name in ('volume_dialog_tap_target_size', 'volume_ringer_drawer_item_size'):
    assert name in native_dimens
    assert float(dimens[name][:-2]) >= 48
assert 2 * float(dimens['volume_ringer_drawer_item_size_half'][:-2]) == float(dimens['volume_ringer_drawer_item_size'][:-2])
assert float(dimens['volume_dialog_tap_target_size'][:-2]) <= float(native_dimens['volume_dialog_panel_width'][:-2])
checks.append('Volume targets reach 48 dp without exceeding native panel width; drawer geometry consistent')

selector = ET.parse(overlay / 'color/borealis_power_content.xml').getroot()
assert selector[0].get(a('state_enabled')) == 'false'
assert float(selector[0].get(a('alpha'))) < 1
assert selector[-1].get(a('state_enabled')) is None
checks.append('Disabled and enabled power actions have separate native color states')


def luminance(hex_color):
    values = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in values]
    return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))


contrasts = {}
for qualifier in ('values', 'values-night'):
    colors = {node.get('name'): node.text for node in ET.parse(overlay / qualifier / 'borealis_native_colors.xml').getroot()}
    for foreground, background in [('borealis_text', 'borealis_surface'),
                                   ('borealis_on_accent', 'borealis_accent')]:
        light, dark = sorted((luminance(colors[foreground]), luminance(colors[background])), reverse=True)
        ratio = (light + .05) / (dark + .05)
        assert ratio >= 4.5, f'{qualifier}: {foreground} contrast {ratio}'
        contrasts[qualifier + '/' + foreground] = round(ratio, 3)
checks.append('Enabled text and progress icons exceed 4.5:1 contrast in both explicit palettes')

files = proof['generated_files'] + [str(relative / 'values/borealis_dimens.xml')]
aapt = root / 'prebuilts/sdk/tools/linux/bin/aapt2'
with tempfile.TemporaryDirectory(prefix='borealis-systemui-resource-test-') as temporary:
    result = subprocess.run([str(aapt), 'compile', '-o', temporary,
                             *[str(package / 'project' / name) for name in files]],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    compiled = len(list(Path(temporary).glob('*.flat')))
    assert compiled == len(files), (compiled, len(files))
checks.append(f'AAPT2 compiled all {compiled} staged resource files')
file_hashes = {name: hashlib.sha256((package / 'project' / name).read_bytes()).hexdigest() for name in files}
report = {'scope': 'Resource syntax, controller binding and palette checks; no APK link/runtime proof',
          'passed': True, 'checks': checks, 'contrast_ratios': contrasts, 'file_sha256': file_hashes,
          'native_apk_linked': False, 'device_tested': False}
(package / 'validation/systemui-resource-tests.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS: {len(checks)} native resource checks; {compiled} AAPT2 resource compilations.')
