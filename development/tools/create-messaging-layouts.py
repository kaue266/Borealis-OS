#!/usr/bin/env python3
"""Modernize SMS list/composer without changing custom view types or binding IDs."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

package=Path(__file__).resolve().parent.parent
source=Path('/home/android/borealisos-android17/packages/apps/Messaging/res')
dest=package/'project/vendor/borealis/overlay/base/packages/apps/Messaging/res'
android='http://schemas.android.com/apk/res/android'
ET.register_namespace('android',android)
ET.register_namespace('app','http://schemas.android.com/apk/res-auto')
a=lambda n:'{'+android+'}'+n
proof=[]

def output(path,tree):
 path.parent.mkdir(parents=True,exist_ok=True)
 ET.indent(tree)
 ET.ElementTree(tree).write(path,encoding='utf-8',xml_declaration=True)

def layout(name,updates,root_updates=None):
 parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
 tree=ET.parse(source/'layout'/name,parser=parser).getroot()
 original={n.get(a('id')):n.tag for n in tree.iter() if n.get(a('id'))}
 if root_updates:
  for key,value in root_updates.items():tree.set(a(key),value)
 for identifier,attrs in updates.items():
  nodes=[n for n in tree.iter() if n.get(a('id'))==identifier]
  assert len(nodes)==1,(name,identifier)
  for key,value in attrs.items():nodes[0].set(a(key),value)
 assert original=={n.get(a('id')):n.tag for n in tree.iter() if n.get(a('id'))}
 output(dest/'layout'/name,tree)
 proof.append({'layout':name,'bindings_preserved':len(original),'updated_ids':list(updates)})

layout('conversation_list_item_view.xml',{
 '@+id/swipeableContent':{'background':'@drawable/borealis_conversation_card',
  'layout_marginStart':'16dp','layout_marginEnd':'16dp','layout_marginTop':'4dp',
  'layout_marginBottom':'4dp','padding':'16dp','minHeight':'88dp','gravity':'center_vertical'},
 '@+id/conversation_name':{'textSize':'17sp','fontFamily':'sans-serif-medium','paddingBottom':'5dp'},
 '@+id/conversation_snippet':{'textSize':'14sp','maxLines':'2','lineSpacingExtra':'2dp'},
 '@+id/conversation_timestamp':{'textSize':'12sp','paddingTop':'4dp'},
})
layout('compose_message_view.xml',{
 '@+id/message_compose_view_container':{'paddingStart':'8dp','paddingEnd':'8dp'},
 '@+id/compose_message_text':{'background':'@drawable/borealis_compose_field',
  'minHeight':'52dp','paddingStart':'16dp','paddingEnd':'16dp','paddingTop':'12dp',
  'paddingBottom':'12dp','textSize':'16sp','textColor':'@color/borealis_text',
  'textColorHint':'@color/borealis_muted'},
 '@+id/attach_media_button':{'minWidth':'48dp','minHeight':'48dp',
  'background':'?android:attr/selectableItemBackgroundBorderless','tint':'@color/borealis_accent'},
 '@+id/send_message_button':{'layout_width':'48dp','layout_height':'48dp',
  'tint':'@color/borealis_on_accent'},
 '@+id/self_send_icon':{'layout_width':'48dp','layout_height':'48dp'},
 '@+id/delete_subject_button':{'minWidth':'48dp','minHeight':'48dp','tint':'@color/borealis_accent'},
})
layout('conversation_list_fragment.xml',{
 '@android:id/list':{'paddingTop':'12dp','paddingBottom':'96dp'},
 '@+id/start_new_conversation_button':{'layout_width':'64dp','layout_height':'64dp',
  'layout_marginEnd':'20dp','layout_marginBottom':'20dp','paddingBottom':'0dp',
  'background':'@drawable/borealis_message_fab','tint':'@color/borealis_on_accent',
  'elevation':'2dp'},
},{'background':'@color/borealis_background'})

def shape(color,radius):
 tree=ET.Element('shape',{a('shape'):'rectangle'})
 ET.SubElement(tree,'solid',{a('color'):color})
 ET.SubElement(tree,'corners',{a('radius'):radius})
 return tree
card=ET.Element('ripple',{a('color'):'@color/borealis_accent'})
ET.SubElement(card,'item').append(shape('@color/borealis_surface','24dp'))
mask=ET.SubElement(card,'item',{a('id'):'@android:id/mask'})
mask.append(shape('@android:color/white','24dp'))
output(dest/'drawable/borealis_conversation_card.xml',card)
field=shape('@color/borealis_surface','26dp')
ET.SubElement(field,'stroke',{a('width'):'1dp',a('color'):'@color/borealis_outline'})
output(dest/'drawable/borealis_compose_field.xml',field)
fab=ET.Element('ripple',{a('color'):'@color/borealis_aurora'})
ET.SubElement(fab,'item').append(shape('@color/borealis_accent','24dp'))
output(dest/'drawable/borealis_message_fab.xml',fab)
(package/'validation/messaging-layouts.json').write_text(json.dumps({
 'layouts':proof,'native_build_passed':False,'sms_runtime_tested':False,
 'preserved':['view types','binding IDs','SIM selection','attachment picker','swipe controllers']},indent=2)+'\n')
print('Generated three native Messaging layouts; retained all custom-view bindings.')
