"""Keep the real APEX service resident on legacy Binder; preserve data and checks."""
import datetime
import hashlib
import json
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'outputs/BorealisOS-Android17/validation/imported-port-review-20261022T230200Z'
backup = json.loads((base / 'latest-apex-lazy-contract.json').read_text())
original_path = Path(backup['directory']) / 'system/bin/apexd'
original = original_path.read_bytes()
original_hash = hashlib.sha256(original).hexdigest()
assert original_hash == '148e4efb4be9138e252e6d2a2d94d13ced8ca5359431c19d461f12fcd57c98db'
assert original[0x3eb7c:0x3eb88].hex() == 'e0030091e1031f2abbf60294'
candidate = bytearray(original)
candidate[0x3eb80:0x3eb84] = bytes.fromhex('21008052')
candidate_hash = hashlib.sha256(candidate).hexdigest()
out = base / ('apex-resident-fix-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
out.mkdir()
(out / 'apexd').write_bytes(candidate)
adb = ['/usr/local/bin/adb', '-s', 'DEVICE_SERIAL']
def read(command, timeout=16):
    result = subprocess.run(adb + ['exec-out', command + '; borealis_rc=$?; printf "\\n__BOREALIS_EXIT__%s\\n" "$borealis_rc"'], capture_output=True, timeout=timeout)
    content, marker, status = result.stdout.rpartition(b'\n__BOREALIS_EXIT__')
    assert result.returncode == 0 and marker and status.strip() == b'0', (command, result.stdout[-300:])
    return content
boot_id = read('cat /proc/sys/kernel/random/boot_id').decode().strip()
assert boot_id == 'a5615958-a7aa-4096-952f-6a9c7c089b5a'
assert read('sha256sum /system/bin/apexd').decode().split()[0] == original_hash
metadata = read('stat -c "%a:%u:%g:%s:%i" /system/bin/apexd').decode().strip()
record = dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), directory=str(out),
              state='prepared', boot_id=boot_id, original_sha256=original_hash, candidate_sha256=candidate_hash,
              backup=str(original_path), original_metadata=metadata,
              patch=dict(offset='0x3eb80', original='e1031f2a', candidate='21008052',
                         meaning='Call LazyServiceRegistrar::forcePersist(true) rather than false after boot completion.'),
              rationale='The real service registers but its legacy Binder client callback is rejected; dropping persistence then exits while SystemServer is using it.',
              security_checks_bypassed=False, caller_identity_forged=False, bpf_success_faked=False,
              limitation='Binder callback/identity incompatibility remains unresolved. This is a resident-service compatibility mode, not a Binder repair.',
              data_erased=False, kernel_changed=False, raw_partition_flash=False, reboot_requested=False)
def save():
    (out / 'application.json').write_text(json.dumps(record, indent=2) + '\n')
    (base / 'latest-apex-resident-fix.json').write_text(json.dumps(record, indent=2) + '\n')
save()
# Pause the reproducibly failing bootstrap loop before replacing its stopped
# dependency. These are init service controls, not a device reset.
read('setprop ctl.stop zygote')
for _ in range(30):
    if read('getprop init.svc.zygote').strip() == b'stopped':
        break
    time.sleep(0.2)
else:
    record['state'] = 'aborted_zygote_not_stopped'
    save()
    read('setprop ctl.start zygote')
    raise RuntimeError('Zygote did not stop; no binary write performed.')
read('setprop ctl.stop apexd')
time.sleep(0.2)
assert not read('pidof apexd; true').strip()
stage = '/data/local/tmp/borealis-apexd-resident'
read('test ! -e ' + stage)
subprocess.run(adb + ['push', str(out / 'apexd'), stage], capture_output=True, check=True, timeout=25)
assert read('sha256sum ' + stage).decode().split()[0] == candidate_hash
read('mount -o remount,rw /')
try:
    assert not read('pidof apexd; true').strip()
    read('cat ' + stage + ' > /system/bin/apexd && sync')
    assert read('sha256sum /system/bin/apexd').decode().split()[0] == candidate_hash
    assert read('stat -c "%a:%u:%g:%s:%i" /system/bin/apexd').decode().strip() == metadata
except BaseException:
    subprocess.run(adb + ['push', str(original_path), stage], capture_output=True, check=True, timeout=25)
    read('cat ' + stage + ' > /system/bin/apexd && sync')
    assert read('sha256sum /system/bin/apexd').decode().split()[0] == original_hash
    record['state'] = 'rolled_back'
    save()
    raise
finally:
    read('mount -o remount,ro /')
    read('setprop ctl.start apexd')
    read('setprop ctl.start zygote')
record.update(state='applied_hash_and_metadata_verified', rollback='With apexd and the failing primary Zygote stopped, restore the verified original file by path; preserve mode/uid/gid/inode/xattrs and return / to ro. Restart those services. No data clearing or partition writes.')
save()
for index in range(6):
    time.sleep(5)
    state = read('cat /proc/uptime; pidof apexd system_server zygote64; service check apexservice; getprop init.svc.bootanim; getprop service.bootanim.exit')
    (out / (str(index) + '-state.txt')).write_bytes(state)
    print(state.decode(errors='replace'), flush=True)
(out / 'logcat.txt').write_bytes(read('logcat -b all -d -t 12000'))
record['test_capture_completed'] = True
save()
print(json.dumps(dict(directory=str(out), state=record['state'], candidate_sha256=candidate_hash), indent=2))
