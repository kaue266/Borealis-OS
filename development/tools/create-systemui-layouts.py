#!/usr/bin/env python3
"""Build native power/volume resources from the pinned Android 17 layouts.

Preserve view classes, controller IDs, progress wrappers and accessibility
bindings. Generating resources does not establish firmware/runtime validation.
"""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

package = Path(__file__).resolve().parent.parent
source = Path('/home/android/borealisos-android17/frameworks/base/packages/SystemUI/res')
dest = package / 'project/vendor/borealis/overlay/base/frameworks/base/packages/SystemUI/res'
android = 'http://schemas.android.com/apk/res/android'
ET.register_namespace('android', android)
ET.register_namespace('androidprv', 'http://schemas.android.com/apk/prv/res/android')
a = lambda name: '{' + android + '}' + name
proof = []
generated = []


def write(name, tree, notice=''):
    path = dest / name
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree)
    xml = ET.tostring(tree, encoding='unicode')
    path.write_text('<?xml version="1.0" encoding="utf-8"?>\n' +
                    (notice.strip() + '\n' if notice.strip() else '') + xml + '\n')
    generated.append(str(path.relative_to(package / 'project')))


def original(name):
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(source / name, parser=parser).getroot()


def binding(tree):
    return [(node.get(a('id')), node.tag) for node in tree.iter()
            if isinstance(node.tag, str) and node.get(a('id'))]


def save_original(name, modify):
    tree = original(name)
    before = binding(tree)
    modify(tree)
    assert binding(tree) == before, name + ': controller binding changed'
    raw = (source / name).read_text()
    prefix = raw[:raw.index('<' + tree.tag)]
    notice = re.sub(r'^\s*<\?xml.*?\?>', '', prefix, flags=re.DOTALL)
    write(name, tree, notice)
    proof.append({'resource': name, 'controller_bindings_preserved': True,
                  'ids': [name for name, tag in before],
                  'source_sha256': hashlib.sha256((source / name).read_bytes()).hexdigest()})


def power_item(tree, lite):
    tree.set(a('minHeight'), '48dp')
    tree.set(a('paddingStart'), '8dp')
    tree.set(a('paddingEnd'), '8dp')
    tree.set(a('paddingTop'), '12dp')
    tree.set(a('paddingBottom'), '12dp')
    if not lite:
        tree.set(a('layout_height'), 'wrap_content')
        tree.set(a('minHeight'), '@dimen/global_actions_grid_item_layout_height')
        tree.set(a('background'), '@drawable/borealis_power_card')
    for node in tree:
        if node.get(a('id')) == '@*android:id/icon':
            node.set(a('tint'), '@color/borealis_power_content')
            if lite:
                node.set(a('background'), '@drawable/borealis_power_button')
            else:
                node.set(a('layout_width'), '24dp')
                node.set(a('layout_height'), '24dp')
        if node.get(a('id')) == '@*android:id/message':
            node.attrib.pop(a('singleLine'), None)
            node.attrib.pop(a('marqueeRepeatLimit'), None)
            node.set(a('ellipsize'), 'end')
            node.set(a('maxLines'), '2')
            node.set(a('textSize'), '14sp')
            node.set(a('fontFamily'), 'sans-serif-medium')
            node.set(a('textColor'), '@color/borealis_power_content')


save_original('layout/global_actions_grid_item_lite.xml', lambda tree: power_item(tree, True))
save_original('layout/global_actions_grid_item_v2.xml', lambda tree: power_item(tree, False))


def shape(radius, color):
    tree = ET.Element('shape', {a('shape'): 'rectangle'})
    ET.SubElement(tree, 'solid', {a('color'): color})
    ET.SubElement(tree, 'corners', {a('radius'): radius})
    ET.SubElement(tree, 'stroke', {a('width'): '1dp', a('color'): '@color/borealis_outline'})
    return tree


for name, radius in [('borealis_power_card', '24dp'), ('borealis_power_button', '20dp')]:
    ripple = ET.Element('ripple', {a('color'): '@color/borealis_systemui_ripple'})
    ET.SubElement(ripple, 'item').append(shape(radius, '@color/borealis_surface'))
    mask = ET.SubElement(ripple, 'item', {a('id'): '@android:id/mask'})
    mask.append(shape(radius, '@android:color/white'))
    write('drawable/' + name + '.xml', ripple)

selector = ET.Element('selector')
ET.SubElement(selector, 'item', {a('state_enabled'): 'false', a('alpha'): '0.38',
                               a('color'): '@color/borealis_text'})
ET.SubElement(selector, 'item', {a('color'): '@color/borealis_text'})
write('color/borealis_power_content.xml', selector)

for qualifier, color in [('values', '#2065469B'), ('values-night', '#30C5B4FF')]:
    values = ET.Element('resources')
    ET.SubElement(values, 'color', name='borealis_systemui_ripple').text = color
    write(qualifier + '/borealis_systemui_interaction.xml', values)


def volume_surface(tree):
    solid = tree.find('solid')
    assert solid is not None
    solid.set(a('color'), '@color/borealis_surface')
    ET.SubElement(tree, 'stroke', {a('width'): '1dp', a('color'): '@color/borealis_outline'})


save_original('drawable/volume_dialog_background.xml', volume_surface)

# The slider's drawable classes and layer IDs are part of VolumeDialogImpl's
# contract. Recoloring keeps that contract; replacing them with plain shapes
# would break progress/icon updates.
def volume_progress(tree):
    progress = tree.find("item[@android:id='@+id/volume_seekbar_progress_solid']/shape/solid",
                         {'android': android})
    assert progress is not None
    progress.set(a('color'), '@color/borealis_accent')
    wrapper = next(node for node in tree.iter()
                   if node.tag == 'com.android.systemui.util.AlphaTintDrawableWrapper')
    wrapper.set(a('tint'), '@color/borealis_on_accent')


save_original('drawable/volume_row_seekbar_progress.xml', volume_progress)

report = {'scope': 'Android 17 native power and volume resources', 'resources': proof,
          'generated_files': generated, 'native_build_passed': False, 'device_tested': False,
          'preserved': ['controller IDs and view classes', 'native action and slider handlers',
                        'native animation and accessibility behavior', 'progress drawable wrappers'],
          'limitations': ['Runtime-tinted and Compose surfaces require firmware inspection.',
                          'These resources do not complete the entire SystemUI redesign.']}
(package / 'validation/systemui-layouts.json').write_text(json.dumps(report, indent=2) + '\n')
print('Generated native power layouts and volume surfaces; firmware validation pending.')
