"""Install only new file-level HAL artifacts; original files are never overwritten."""
import datetime,hashlib,json,shlex,shutil,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
base=root/'outputs/BorealisOS-Android17/validation/imported-port-review-20261022T230200Z'
candidate=json.loads((base/'latest-lights-hal-candidate.json').read_text())
out=Path(candidate['directory']); adb=['/usr/local/bin/adb','-s','DEVICE_SERIAL']
def command(s,timeout=20):
 p=subprocess.run(adb+['exec-out',s+'; borealis_rc=$?; printf "\\n__BOREALIS_EXIT__%s\\n" "$borealis_rc"'],capture_output=True,timeout=timeout)
 content,marker,status=p.stdout.rpartition(b'\n__BOREALIS_EXIT__')
 assert p.returncode==0 and marker and status.strip()==b'0',(s,p.stdout[-700:],p.stderr[-200:])
 return content.decode(errors='replace').strip()
record={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'state':'preparing','changes':[],'raw_partition_flash':False,'kernel_changed':False,'data_erased':False,'phone_reboot':False}
def save():
 (out/'application.json').write_text(json.dumps(record,indent=2)+'\n')
 (base/'latest-lights-hal-application.json').write_text(json.dumps(record,indent=2)+'\n')
record['boot_id']=command('cat /proc/sys/kernel/random/boot_id')
record['mounts_before']=command('cat /proc/mounts')
assert command('pidof system_server')=='25778'
assert command('pidof android.hardware.light-service.borealis; true')==''
backup=Path(json.loads((base/'latest-pre-gpu-backup.json').read_text())['directory'])/'additional-controls-repair'
backup.mkdir(exist_ok=True)
artifacts=[('android.hardware.light-service.borealis','/system/bin/hw/android.hardware.light-service.borealis','755'),('borealis-lights.rc','/system/etc/init/borealis-lights.rc','644'),('borealis-lights.xml','/vendor/etc/vintf/manifest/borealis-lights.xml','644')]
for local,remote,mode in artifacts:
 assert command('test ! -e '+shlex.quote(remote))==''
 source=out/local
 assert source.exists()
 shutil.copy2(source,backup/local)
 stage='/data/local/tmp/'+local
 subprocess.run(adb+['push',str(source),stage],capture_output=True,check=True,timeout=20)
 assert command('sha256sum '+stage).split()[0]==hashlib.sha256(source.read_bytes()).hexdigest()
command('chmod 755 /data/local/tmp/android.hardware.light-service.borealis')
record['declared_before']=command('/data/local/tmp/android.hardware.light-service.borealis --declared')
print(record['declared_before'],flush=True)
save()
command('mount -o remount,rw / && mount -o remount,rw /vendor')
try:
 command('mkdir -p /system/bin/hw /vendor/etc/vintf/manifest')
 for local,remote,mode in artifacts:
  stage='/data/local/tmp/'+local
  command('cp '+shlex.quote(stage)+' '+shlex.quote(remote)+' && chown 0:0 '+shlex.quote(remote)+' && chmod '+mode+' '+shlex.quote(remote))
  sha=command('sha256sum '+shlex.quote(remote)).split()[0]
  assert sha==hashlib.sha256((out/local).read_bytes()).hexdigest()
  record['changes'].append({'new_file':remote,'sha256':sha,'mode':mode,'rollback':'Remove only this new file with service stopped; no original file existed.'})
  save()
finally:
 command('sync; mount -o remount,ro /vendor && mount -o remount,ro /')
record['declared_after']=command('/data/local/tmp/android.hardware.light-service.borealis --declared')
record['state']='installed_files_verified_runtime_not_started'
save()
(backup/'application.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2),flush=True)
