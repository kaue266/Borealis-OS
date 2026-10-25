"""Persist one explicit per-flag compatibility setting; preserve rollback."""
import datetime
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/BorealisOS-Android17/validation/imported-port-review-20261022T230200Z'
app=json.loads((BASE/'latest-connectivity-repairs.json').read_text())
OUT=Path(app['directory'])
BACKUP=Path(app['efs_backup']).parent
ADB=[r'F:\platform-tools\adb.exe','-s','DEVICE_SERIAL']
def run(*args,timeout=20):
    p=subprocess.run(ADB+list(args),capture_output=True,timeout=timeout)
    if p.returncode:raise RuntimeError((args,p.stdout[-800:],p.stderr[-800:]))
    return p.stdout
def sh(s,**kw):return run('shell',s,**kw)
assert run('get-state').strip()==b'device'
assert sh('getprop init.svc.borealis-connectivity-diagnostics').strip()==b'stopped'
path='/system/etc/borealis-connectivity-diagnostics.sh'
before=run('exec-out','cat',path)
assert hashlib.sha256(before).hexdigest()=='653d705da68940e0bb67576d6aa75923375cf623fc71670aafe6df886de185e4'
old=b'/system/bin/device_config put connectivity data_stall_evaluation_type 1\necho "device_config_put_exit=$?"'
new=b'# Pin only this optional TCP-stall flag; keep global configuration sync enabled.\n/system/bin/device_config override connectivity data_stall_evaluation_type 1\necho "device_config_override_exit=$?"'
assert before.count(old)==1
after=before.replace(old,new)
(OUT/'diagnostic-script.before-sticky.sh').write_bytes(before)
(OUT/'diagnostic-script.sticky.sh').write_bytes(after)
for n in ['diagnostic-script.before-sticky.sh','diagnostic-script.sticky.sh']:shutil.copy2(OUT/n,BACKUP/n)
original_overrides=sh('device_config list_local_overrides').decode()
assert not any('connectivity/data_stall_evaluation_type' in s or 'connectivity:data_stall_evaluation_type' in s for s in original_overrides.splitlines()),original_overrides
previous_value=sh('device_config get connectivity data_stall_evaluation_type').decode().strip()
assert previous_value in ('null','1'),previous_value
meta=sh('stat -c %a:%u:%g:%i '+path).strip()
run('push',str(OUT/'diagnostic-script.sticky.sh'),'/data/local/tmp/borealis-diagnostics-sticky.sh')
run('push',str(OUT/'diagnostic-script.before-sticky.sh'),'/data/local/tmp/borealis-diagnostics-before-sticky.sh')
sh('sh -n /data/local/tmp/borealis-diagnostics-sticky.sh')
mounts=sh('cat /proc/mounts').decode()
rootmount=[line for line in mounts.splitlines() if line.split()[1]=='/']
assert len(rootmount)==1 and rootmount[0].split()[2]=='ext4'
sh('mount -o remount,rw /')
try:
    sh('cat /data/local/tmp/borealis-diagnostics-sticky.sh > '+path)
    assert run('exec-out','cat',path)==after
    assert sh('stat -c %a:%u:%g:%i '+path).strip()==meta
except BaseException:
    sh('cat /data/local/tmp/borealis-diagnostics-before-sticky.sh > '+path)
    raise
finally:
    sh('sync; mount -o remount,ro /')
override_output=sh('device_config override connectivity data_stall_evaluation_type 1').decode()
readback=sh('device_config get connectivity data_stall_evaluation_type').decode().strip()
assert readback=='1',readback
result={'applied_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'previous_value':previous_value,'previous_local_overrides':original_overrides,
        'per_flag_override':'connectivity/data_stall_evaluation_type=1',
        'global_sync_mode':sh('device_config get_sync_disabled_for_tests').decode().strip(),
        'readback':readback,'override_output':override_output,
        'script_before_sha256':hashlib.sha256(before).hexdigest(),'script_after_sha256':hashlib.sha256(after).hexdigest(),
        'script_was_stopped_before_update':True,
        'rollback':'device_config clear_override connectivity data_stall_evaluation_type; restore underlying prior value if changed; restore or remove diagnostics script as documented'}
(OUT/'sticky-setting-application.json').write_text(json.dumps(result,indent=2)+'\n')
shutil.copy2(OUT/'sticky-setting-application.json',BACKUP/'sticky-setting-application.json')
print(json.dumps(result,indent=2))
