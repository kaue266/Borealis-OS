"""Restore only the standard /mnt propagation skipped by imported init patch."""
import datetime,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/BorealisOS-Android17/validation/imported-port-review-20261022T230200Z'
PREVIOUS=Path(json.loads((BASE/'latest-storage-fuse-repair.json').read_text())['directory'])
OUT=PREVIOUS.parent/('storage-propagation-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
OUT.mkdir()
ADB=[r'F:\platform-tools\adb.exe','-s','DEVICE_SERIAL']
def run(*args,timeout=30):
 p=subprocess.run(ADB+list(args),capture_output=True,timeout=timeout)
 if p.returncode:raise RuntimeError((args,p.stdout[-700:],p.stderr[-700:]))
 return p.stdout
def sh(command):return run('shell',command)
remote='/system/etc/init/borealis-connectivity-diagnostics.rc'
before=run('exec-out','cat',remote)
assert hashlib.sha256(before).hexdigest()=='b50673dcb113c5f2cf05c1767954017953d3e62e08bd3614af871f08b51895c4'
assert b'emulated;0 unmountable' in sh('sm list-volumes all')
assert sh('getprop init.svc.borealis-connectivity-diagnostics').strip()==b'stopped'
processes=sh('ps -A -o PID,NAME').decode()
media=[int(line.split()[0]) for line in processes.splitlines() if line.rstrip().endswith('com.android.providers.media.module')]
assert len(media)==1
initmounts=sh('cat /proc/1/mountinfo')
mediamounts=sh('cat /proc/'+str(media[0])+'/mountinfo')
assert b'shared:' not in next(line for line in initmounts.splitlines() if line.split()[4]==b'/mnt')
assert b'/pass_through/0 /storage' in mediamounts
assert b'/data/media' not in mediamounts
(OUT/'init-mountinfo-before.txt').write_bytes(initmounts)
(OUT/'media-mountinfo-before.txt').write_bytes(mediamounts)
(OUT/'diagnostics.rc.before').write_bytes(before)
original=(PREVIOUS/'diagnostics.rc.before').read_bytes()
assert hashlib.sha256(original).hexdigest()=='cb80942aa83611c9355aa86ffa419eabe5bb984ce76472bef0fb0590f10e8ad8'
payload=original+b'''
# Restore storage propagation skipped by imported SetupMountNamespaces stub.
# Match /mnt setup in AOSP init; keep application namespaces and FUSE isolation.
on init
    mount none /mnt /mnt shared rec
    mkdir /mnt/installer 0755 root root
    mkdir /mnt/androidwritable 0755 root root
    mount none /mnt/user /mnt/installer bind rec
    mount none /mnt/user /mnt/androidwritable bind rec
    mount none /mnt/installer /mnt/installer slave
    mount none /mnt/androidwritable /mnt/androidwritable slave
    mount none /mnt/installer /mnt/installer shared
    mount none /mnt/androidwritable /mnt/androidwritable shared
'''
local=OUT/'borealis-storage-propagation.rc';local.write_bytes(payload)
# Validate with the real init parser before touching the installed file.
wsl='/mnt/c/'+str(local)[3:].replace('\\','/')
v=subprocess.run(['wsl','-d','Ubuntu-24.04','--','/home/android/borealisos-android17/out/host/linux-x86/bin/host_init_verifier',wsl],capture_output=True,timeout=30)
(OUT/'init-verifier.txt').write_bytes(v.stdout+v.stderr)
assert v.returncode==0,(v.stdout,v.stderr)
meta=sh('stat -c %a:%u:%g:%i '+remote)
context=sh('ls -ldZ '+remote)
for content,remote_tmp in [(payload,'/data/local/tmp/borealis-storage-propagation.rc'),
                           (before,'/data/local/tmp/borealis-storage-propagation-before.rc')]:
 p=subprocess.run(ADB+['shell','cat > '+remote_tmp],input=content,capture_output=True,timeout=20)
 assert p.returncode==0,p.stderr
 assert run('exec-out','cat',remote_tmp)==content
sh('mount -o remount,rw /')
try:
 sh('cat /data/local/tmp/borealis-storage-propagation.rc > '+remote)
 assert run('exec-out','cat',remote)==payload
 assert sh('stat -c %a:%u:%g:%i '+remote)==meta
 assert sh('ls -ldZ '+remote).split()[3]==context.split()[3]
except BaseException:
 sh('cat /data/local/tmp/borealis-storage-propagation-before.rc > '+remote)
 assert run('exec-out','cat',remote)==before
 raise
finally:sh('sync; mount -o remount,ro /')
record={'state':'applied_readback_verified_restart_required','directory':str(OUT),'target':remote,
 'before_sha256':hashlib.sha256(before).hexdigest(),'sha256':hashlib.sha256(payload).hexdigest(),
 'reason':'Imported SetupMountNamespaces stub skipped shared /mnt and installer/writable slave aliases; MediaProvider inherited empty private storage view.',
 'fuse_only_experiment_removed':True,'kernel_changed':False,'data_deleted':False,
 'inode_owner_mode_context_preserved':True,'app_isolation_preserved':True,
 'rollback':'Restore diagnostics.rc.before in-place then reboot; restore original cb80942 config to remove both storage experiments.'}
for path in [OUT/'application.json',BASE/'latest-storage-propagation-repair.json']:
 path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
backup=Path(r'F:\BorealisOS-A30-backup-antes-GPU-20261024T161605Z\additional-controls-repair')/OUT.name
shutil.copytree(OUT,backup)
print(json.dumps(record,indent=2))
