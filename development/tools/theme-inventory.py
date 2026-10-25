#!/usr/bin/env python3
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

source=Path('/home/android/borealisos-android17')
output=Path(__file__).resolve().parent.parent/'validation'
paths=['frameworks/base/core/res/res','frameworks/base/packages/SystemUI/res',
       'packages/apps/Settings/res','packages/apps/Launcher3/res',
       'packages/apps/Contacts/res','packages/apps/Dialer/java/com/android/dialer/theme/hidden/res',
       'packages/apps/Dialer/java/com/android/dialer/theme/base/res',
       'packages/apps/Dialer/java/com/android/dialer/theme/common/res',
       'packages/apps/Messaging/res','packages/apps/DeskClock/res',
       'packages/apps/DocumentsUI/res','packages/apps/Camera2/res',
       'packages/apps/Gallery2/res','packages/inputmethods/LatinIME/java/res']
inventory={}
for name in paths:
    values={}
    for file in sorted((source/name/'values').glob('*.xml')):
        try: tree=ET.parse(file)
        except ET.ParseError: continue
        for item in tree.getroot():
            key=item.get('name')
            if key and item.tag in ('color','dimen','style','string'):
                values[key]={'type':item.tag,'value':(item.text or '').strip(),
                             'parent':item.get('parent'),'file':str(file.relative_to(source))}
    inventory[name]=values
    candidates=[k for k,v in values.items() if v['type']=='color' and
                re.search('background|primary|accent|surface|text',k)]
    print(name,':',', '.join(candidates[:24]),flush=True)
output.mkdir(exist_ok=True)
(output/'theme-resource-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
