"""Build only the small missing userspace HAL using frozen AIDL V1 and existing NDK."""
import datetime,hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
r=Path('/home/android/borealisos-android17')
base=root/'outputs/BorealisOS-Android17/validation/imported-port-review-20261022T230200Z'
out=base/('lights-hal-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
out.mkdir(); gen=out/'generated'; gen.mkdir(); inc=out/'include'; inc.mkdir()
api=r/'hardware/interfaces/light/aidl/aidl_api/android.hardware.light/1'
def run(args):
 p=subprocess.run([str(a) for a in args],capture_output=True)
 (out/'build.log').open('ab').write(p.stdout+p.stderr)
 if p.returncode: raise RuntimeError((p.stdout+p.stderr).decode(errors='replace')[-6500:])
for path in sorted((api/'android/hardware/light').glob('*.aidl')):
 run([r/'out/host/linux-x86/bin/aidl','--lang=ndk','--structured','--version','1','--hash','33fec8401b6e66bddaeff251e1a2a0f4fa0d3bee','--stability','vintf','--min_sdk_version','37','-I'+str(api),'-h',inc,'-o',gen,path])
clang=r/'prebuilts/clang/host/linux-x86/clang-r584948b'
source=root/'work/a30-light-service.cpp'
dest=out/'android.hardware.light-service.borealis'
crt=r/'out/soong/.intermediates/bionic/libc'
begin=crt/'crtbegin_dynamic/android_arm64_armv8-a_cortex-a53/crtbegin_dynamic.o'
end=crt/'crtend_android/android_arm64_armv8-a_cortex-a53/crtend_android.o'
assert begin.exists() and end.exists()
run([clang/'bin/clang++','--target=aarch64-linux-android37','--sysroot='+str(r/'out/soong/ndk/sysroot'),'-std=c++17','-O2','-fPIE','-pie','-fno-exceptions','-fno-rtti','-D__ANDROID_UNAVAILABLE_SYMBOLS_ARE_WEAK__','-D__ANDROID_APEX__=0','-I'+str(inc),'-I'+str(r/'frameworks/native/libs/binder/ndk/include_platform'),'-I'+str(r/'frameworks/native/libs/binder/ndk/include_cpp'),'-I'+str(r/'frameworks/native/libs/binder/ndk/include_ndk'),'-isystem',clang/'include/c++/v1','-nostartfiles',begin,source,*sorted(gen.rglob('*.cpp')),'-L'+str(r/'out/target/product/a30/system/lib64'),'-nostdlib++','-lc++','-lbinder_ndk','-llog',end,'-o',dest])
rc='service borealis-lights-hal /system/bin/hw/android.hardware.light-service.borealis\n    class hal\n    user system\n    group system\n    interface aidl android.hardware.light.ILights/default\n'
manifest='<manifest version="1.0" type="device">\n  <hal format="aidl">\n    <name>android.hardware.light</name>\n    <version>1</version>\n    <fqname>ILights/default</fqname>\n  </hal>\n</manifest>\n'
(out/'borealis-lights.rc').write_text(rc)
(out/'borealis-lights.xml').write_text(manifest)
record={'directory':str(out),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'binary_bytes':dest.stat().st_size,'frozen_aidl_version':1,'compiled_scope':'Only small userspace backlight HAL; no kernel/ROM build','phone_installed':False,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
(out/'candidate.json').write_text(json.dumps(record,indent=2)+'\n')
(base/'latest-lights-hal-candidate.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2),flush=True)
