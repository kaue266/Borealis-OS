#!/usr/bin/env python3
"""Install the exact old vendor ABI libraries needed by Samsung's existing blobs."""
from pathlib import Path
import base64
import difflib
import hashlib
import json
import re
import subprocess
import urllib.request

package=Path(__file__).resolve().parent.parent
root=Path('/home/android/borealisos-android17')
compat=root/'hardware/lineage/compat'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=compat,text=True).strip()=='9e8811a297036c370f7643813a3c733f6e442d86'
original=subprocess.check_output(['git','show','HEAD:Android.bp'],cwd=compat,text=True)
selected=[]
for match in re.finditer(r'^([a-z_]+)\s*\{',original,re.M):
 start=match.start();depth=0;quoted=False;escape=False
 for index in range(original.index('{',start),len(original)):
  ch=original[index]
  if quoted:
   if escape:escape=False
   elif ch=='\\':escape=True
   elif ch=='"':quoted=False
  elif ch=='"':quoted=True
  elif ch=='{':depth+=1
  elif ch=='}':
   depth-=1
   if depth==0:break
 block=original[start:index+1]
 name=re.search(r'\bname:\s*"([^"]+)"',block)
 if match.group(1) in ('package','license') or name and name.group(1) in ('libcrypto-v33','libcrypto_shim'):
  selected.append(block)
assert any('name: "libcrypto-v33"' in s for s in selected)
assert any('name: "libcrypto_shim"' in s for s in selected)
after='// Borealis AOSP: only the Samsung-required compatibility libraries.\n\n'+'\n\n'.join(selected)+'\n'
(compat/'Android.bp').write_text(after)
proof=package/'validation/port';proof.mkdir(parents=True,exist_ok=True)
(proof/'hardware__lineage__compat__Android.bp.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),after.splitlines(True),fromfile='a/hardware/lineage/compat/Android.bp',tofile='b/hardware/lineage/compat/Android.bp')))

commit='f8e09ad360e0904fb5a14c2dfd4d879d03d81dfa'
destination=package/'project/vendor/borealis/compat/protobuf391'
files=['Android.bp','LICENSE']+[f'{arch}/libprotobuf-cpp-{kind}-3.9.1.so' for arch in ('arm','arm64') for kind in ('full','lite')]
checksums={}
for name in files:
 url=f'https://android.googlesource.com/platform/prebuilts/misc/+/{commit}/protobuf_vendorcompat/{name}?format=TEXT'
 path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
 if not path.is_file():
  data=base64.b64decode(urllib.request.urlopen(url,timeout=90).read())
  if name.endswith('.so'):assert data[:4]==b'\x7fELF'
  path.write_bytes(data)
 data=path.read_bytes()
 if name=='Android.bp':
  data=data.replace(b'prebuilts_misc_protobuf_vendorcompat_license',b'borealis_protobuf391_license')
  path.write_bytes(data)
 checksums[name]=hashlib.sha256(data).hexdigest()
 target=root/'vendor/borealis/compat/protobuf391'/name
 target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
(proof/'vendor-compat.json').write_text(json.dumps({'lineage_compat_commit':'9e8811a297036c370f7643813a3c733f6e442d86',
 'aosp_protobuf_commit':commit,'protobuf_files_sha256':checksums,
 'purpose':'Samsung blob ABI, not replacement Android platform libraries','runtime_verified':False},indent=2)+'\n')
print('Installed real crypto v33 and protobuf 3.9.1 ABI compatibility libraries; runtime verification pending.')
