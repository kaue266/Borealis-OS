#!/usr/bin/env python3
"""Audit the real vendor Mali binaries and kernel UAPI; never replace drivers."""
from pathlib import Path
import subprocess,json,hashlib,re
package=Path(__file__).resolve().parent.parent
root=Path('/home/android/borealisos-android17')
kernel=Path('/home/android/nebula-r24u-android17')
vendor=root/'vendor/samsung/exynos7885-common/proprietary'
report={'kernel_source':'drivers/gpu/arm/b_r26p0','libraries':[],
 'android17_runtime_compatibility':'unverified','userspace_driver_rebuilt':False,
 'source_availability':'Kernel-space source available; vendor Mali userspace supplied as ELF prebuilts.'}
for path in sorted(vendor.rglob('libGLES_mali.so')):
 if path.is_symlink():continue
 header=subprocess.check_output(['readelf','-h',str(path)],text=True)
 dynamic=subprocess.check_output(['readelf','-d',str(path)],text=True)
 notes=subprocess.check_output(['readelf','-n',str(path)],text=True)
 versions=subprocess.check_output(['strings','-a',str(path)],text=True,errors='replace')
 markers=sorted(set(line.strip() for line in versions.splitlines() if re.search(r'(?<!\w)r\d+p\d+(?!\w)',line) and len(line)<220))
 report['libraries'].append({'path':str(path.relative_to(root)),
  'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,
  'elf_class':re.search(r'Class:\s+(\S+)',header).group(1),
  'machine':re.search(r'Machine:\s+(.+)',header).group(1).strip(),
  'needed':re.findall(r'\(NEEDED\).*\[(.+?)\]',dynamic),
  'soname':re.findall(r'\(SONAME\).*\[(.+?)\]',dynamic),
  'build_id':re.findall(r'Build ID: (\w+)',notes), 'ddk_markers':markers[:10]})
headers={}
for path in (kernel/'drivers/gpu/arm/b_r26p0').rglob('*.h'):
 if path.name in ('mali_kbase_ioctl.h','mali_kbase_uk.h','mali_kbase_uku.h'):
  relative=str(path.relative_to(kernel))
  original=subprocess.check_output(['git','-C',str(kernel),'show','HEAD:'+relative])
  headers[relative]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
    'matches_original_r24u':original==path.read_bytes()}
report['kernel_uapi_headers']=headers
report['gralloc_sources']=[str(p.relative_to(root)) for p in (root/'hardware/samsung_slsi-linaro/graphics').rglob('Android.*')
 if 'gralloc' in str(p.parent).lower()]
assert len(report['libraries'])==2,'Expected real 32-bit and 64-bit vendor Mali libraries'
assert set(p['elf_class'] for p in report['libraries'])=={'ELF32','ELF64'}
assert headers and all(p['matches_original_r24u'] for p in headers.values())
output=package/'validation/mali-stack.json'
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
