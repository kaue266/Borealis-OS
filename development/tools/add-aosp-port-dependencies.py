#!/usr/bin/env python3
"""Pin public vendor-only dependencies assumed by the Lineage hardware trees."""
from pathlib import Path
import json
import subprocess
import xml.etree.ElementTree as ET
root=Path('/home/android/borealisos-android17')
output=Path(__file__).resolve().parent.parent/'validation'
projects=[
 ('device/lineage/sepolicy','android_device_lineage_sepolicy','0a9e75292f0ed1a83c31a311b1b32367a9faff75'),
 ('hardware/lineage/interfaces','android_hardware_lineage_interfaces','805d25348106e8cc6f378c0b153789f3cf8da667'),
 ('hardware/google/pixel','android_hardware_google_pixel','8d371222290203e232f2e2b88cb86eb9d23e98de'),
 ('hardware/samsung_slsi-linaro/interfaces','android_hardware_samsung_slsi-linaro_interfaces','a23ed82b3f3859aa9e0207036b0d0e98119b959b'),
 ('hardware/lineage/compat','android_hardware_lineage_compat','9e8811a297036c370f7643813a3c733f6e442d86'),
]
manifest=ET.Element('manifest')
ET.SubElement(manifest,'remote',name='borealis-lineage-vendor',fetch='https://github.com/LineageOS/')
for path,name,commit in projects:
 ET.SubElement(manifest,'project',path=path,name=name,revision=commit,remote='borealis-lineage-vendor',**{'clone-depth':'1'})
ET.indent(manifest)
file=root/'.repo/local_manifests/borealis-vendor-compat.xml'
ET.ElementTree(manifest).write(file,encoding='utf-8',xml_declaration=True)
(output/'vendor-dependencies.json').write_text(json.dumps({
 'purpose':'Vendor HAL interfaces and policy only; no Lineage system, Google apps or updater',
 'reference_branch':'lineage-23.2','projects':[dict(path=p,name=n,commit=c) for p,n,c in projects]},indent=2)+'\n')
with (Path('/home/android/borealisos-android17-logs')/'sync-vendor-deps.log').open('w') as log:
 pending=[p for p,_,_ in projects if not (root/p/'.git').exists()]
 result=subprocess.run(['repo','sync','-c','-j2','--no-clone-bundle','--no-tags','--fail-fast']+pending,cwd=root,stdout=log,stderr=subprocess.STDOUT) if pending else subprocess.CompletedProcess([],0)
if result.returncode:
 print(log.name);raise SystemExit(result.returncode)
with (Path('/home/android/borealisos-android17-logs')/'source-lock.xml').open('w') as log:
 subprocess.run(['repo','manifest','-r'],cwd=root,stdout=log,check=True)
print('Vendor dependencies synchronized at fixed commits.')
