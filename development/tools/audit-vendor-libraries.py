#!/usr/bin/env python3
"""Find literal library names absent from the synced Android 17 module inventory.

This is a localization aid; Soong remains the authoritative dependency validator.
"""
from pathlib import Path
import json
import re
root=Path('/home/android/borealisos-android17')
files=(root/'out/.module_paths/Android.bp.list').read_text().splitlines()
known=set()
for name in files:
 file=root/name
 if file.is_file():known.update(re.findall(r'\bname:\s*"([^"]+)"',file.read_text(errors='replace')))
missing={}
for directory in ('vendor/samsung','device/samsung','hardware/samsung_slsi-linaro','hardware/samsung'):
 for file in (root/directory).rglob('Android.bp'):
  text=file.read_text()
  for group in re.findall(r'\b(?:shared_libs|static_libs|header_libs|whole_static_libs):\s*\[(.*?)\]',text,re.S):
   for name in re.findall(r'"([^"]+)"',group):
    if not (name.startswith('lib') or name.startswith('android.hardware.') and '@' in name):continue
    if name not in known:
     missing.setdefault(name,[]).append(str(file.relative_to(root)))
output=Path(__file__).resolve().parent.parent/'validation/port/vendor-libraries.json'
output.write_text(json.dumps({'scope':'Literal names; generated/conditional module names need Soong confirmation','missing_candidates':missing},indent=2)+'\n')
for name,locations in missing.items():print(name,':',', '.join(sorted(set(locations))))
