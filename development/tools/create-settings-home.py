#!/usr/bin/env python3
"""Native Borealis Settings homepage header; retain AOSP scrolling and search."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

package=Path(__file__).resolve().parent.parent
source=Path('/home/android/borealisos-android17/packages/apps/Settings/res')
dest=package/'project/vendor/borealis/overlay/base/packages/apps/Settings/res'
ns='http://schemas.android.com/apk/res/android'
ET.register_namespace('android',ns)
ET.register_namespace('app','http://schemas.android.com/apk/res-auto')
a=lambda n:'{'+ns+'}'+n
parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
tree=ET.parse(source/'layout/settings_homepage_container.xml',parser).getroot()
bindings={n.get(a('id')):n.tag for n in tree.iter() if n.get(a('id'))}
container=[n for n in tree.iter() if n.get(a('id'))=='@+id/homepage_container']
assert len(container)==1
header=ET.Element('LinearLayout',{
 a('layout_width'):'match_parent',a('layout_height'):'wrap_content',
 a('orientation'):'vertical',a('paddingStart'):'24dp',a('paddingEnd'):'24dp',
 a('paddingTop'):'24dp',a('paddingBottom'):'24dp',
})
ET.SubElement(header,'TextView',{
 a('layout_width'):'match_parent',a('layout_height'):'wrap_content',
 a('text'):'@string/borealis_home_eyebrow',a('textSize'):'11sp',
 a('textColor'):'@color/borealis_aurora',a('letterSpacing'):'0.12',
 a('fontFamily'):'sans-serif-medium',
})
ET.SubElement(header,'TextView',{
 a('layout_width'):'match_parent',a('layout_height'):'wrap_content',
 a('text'):'@string/borealis_home_headline',a('textSize'):'36sp',
 a('textColor'):'@color/borealis_text',a('fontFamily'):'borealis-orbit',
 a('layout_marginTop'):'12dp',a('lineSpacingMultiplier'):'1.08',
 a('accessibilityHeading'):'true',
})
ET.SubElement(header,'TextView',{
 a('layout_width'):'match_parent',a('layout_height'):'wrap_content',
 a('text'):'@string/borealis_home_detail',a('textSize'):'14sp',
 a('textColor'):'@color/borealis_muted',a('layout_marginTop'):'10dp',
})
container[0].insert(0,header)
assert bindings=={n.get(a('id')):n.tag for n in tree.iter() if n.get(a('id'))}

def output(path,element):
 path.parent.mkdir(parents=True,exist_ok=True)
 ET.indent(element)
 ET.ElementTree(element).write(path,encoding='utf-8',xml_declaration=True)
output(dest/'layout/settings_homepage_container.xml',tree)
for qualifier,strings in {
 'values':{'borealis_home_eyebrow':'BOREALIS · AURORA',
  'borealis_home_headline':'Your universe.\\nYour way.',
  'borealis_home_detail':'Appearance, energy and privacy in your orbit.'},
 'values-pt-rBR':{'borealis_home_eyebrow':'BOREALIS · AURORA',
  'borealis_home_headline':'Seu universo.\\nDo seu jeito.',
  'borealis_home_detail':'Aparência, energia e privacidade na sua órbita.'},
 'values-es':{'borealis_home_eyebrow':'BOREALIS · AURORA',
  'borealis_home_headline':'Tu universo.\\nA tu manera.',
  'borealis_home_detail':'Apariencia, energía y privacidad en tu órbita.'},
}.items():
 resources=ET.Element('resources')
 for name,value in strings.items():ET.SubElement(resources,'string',name=name).text=value
 output(dest/qualifier/'borealis_home.xml',resources)
(package/'validation/settings-home.json').write_text(json.dumps({
 'preserved_bindings':len(bindings),'search_and_scrolling':'AOSP native controllers',
 'header_font':'borealis-orbit','body_font':'system default',
 'native_build_passed':False,'device_layout_tested':False,
},indent=2)+'\n')
print('Native Settings homepage header generated; AOSP binding IDs retained.')
