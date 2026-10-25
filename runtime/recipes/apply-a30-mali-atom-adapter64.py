"""Apply the tested file-level GPU adapter in recovery, with verified reversal."""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'outputs/BorealisOS-Android17/validation/imported-port-review-20261022T230200Z'
candidate = json.loads((base / 'latest-mali-atom-adapter64.json').read_text())
backup = json.loads((base / 'latest-pre-gpu-backup.json').read_text())
assert backup['state'] == 'verified' and candidate['all_tests_passed']
assert len(candidate['emulation_tests']) == 11
directory = Path(candidate['directory'])
local = directory / 'libGLES_mali.so'
assert hashlib.sha256(local.read_bytes()).hexdigest() == candidate['candidate_sha256']
original_backup = Path(backup['directory']) / 'files/vendor/lib64/egl/libGLES_mali.so'
assert hashlib.sha256(original_backup.read_bytes()).hexdigest() == candidate['source_sha256']
adb = ['/usr/local/bin/adb', '-s', 'DEVICE_SERIAL']
target = '/vendor/lib64/egl/libGLES_mali.so'
stage = '/vendor/lib64/egl/.borealis-atom-adapter64-v1.tmp'
old = '/vendor/lib64/egl/.borealis-before-atom-adapter64-v1'

def command(text, timeout=35):
    result = subprocess.run(adb + ['exec-out', text + '; borealis_rc=$?; printf "\\n__BOREALIS_EXIT__%s\\n" "$borealis_rc"'], capture_output=True, timeout=timeout)
    content, marker, status = result.stdout.rpartition(b'\n__BOREALIS_EXIT__')
    assert result.returncode == 0 and marker and status.strip() == b'0', (text, result.stdout[-300:], result.stderr[-150:])
    return content.decode(errors='replace').strip()

assert subprocess.check_output(adb + ['get-state'], timeout=10).strip() == b'recovery'
assert command('cat /proc/sys/kernel/random/boot_id') == backup['recovery_boot_id']
assert command('sha256sum ' + target).split()[0] == candidate['source_sha256']
assert command('sha256sum /dev/block/by-name/boot', timeout=45).split()[0] == '397dacba79038cf5375907dc3868336e56e18600ece2c547acd3899ed167d354'
mounts = command('cat /proc/mounts')
assert any(line.split()[1] == '/vendor' and 'rw' in line.split()[3].split(',') for line in mounts.splitlines())
assert command('stat -c "%a %u %g %s" ' + target) == '644 0 0 52100080'
assert command('pidof surfaceflinger bootanimation zygote zygote64 system_server; true') == ''
command('test ! -e ' + stage + ' && test ! -e ' + old)
record = dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), state='staging',
              candidate_sha256=candidate['candidate_sha256'], original_sha256=candidate['source_sha256'],
              target=target, on_device_backup=old, local_backup=str(original_backup),
              kernel_changed=False, raw_partition_flash=False, phone_reboot=False, data_erased=False,
              scope='One userspace Mali64 library. Atom repacking plus restoration of original callbacks/error handling.',
              rollback='While in recovery and with no graphics processes, verify backup hash, rename the candidate aside, restore the original file from on_device_backup, preserve uid/gid 0:0, mode 0644 and same_process_hal_file SELinux label.')
def save():
    (directory / 'application.json').write_text(json.dumps(record, indent=2) + '\n')
    (base / 'latest-mali-atom-adapter64-application.json').write_text(json.dumps(record, indent=2) + '\n')
save()
subprocess.run(adb + ['push', str(local), stage], check=True, capture_output=True, timeout=90)
assert command('sha256sum ' + stage).split()[0] == candidate['candidate_sha256']
command('chown 0:0 ' + stage + ' && chmod 0644 ' + stage + ' && chcon u:object_r:same_process_hal_file:s0 ' + stage)
assert 'u:object_r:same_process_hal_file:s0' in command('ls -ldZ ' + stage)
command('mv ' + target + ' ' + old)
try:
    command('mv ' + stage + ' ' + target)
    assert command('sha256sum ' + target).split()[0] == candidate['candidate_sha256']
    assert command('stat -c "%a %u %g %s" ' + target) == '644 0 0 52100080'
    assert 'u:object_r:same_process_hal_file:s0' in command('ls -ldZ ' + target)
    assert command('sha256sum ' + old).split()[0] == candidate['source_sha256']
except BaseException:
    record['state'] = 'verification_failed_restoring_original'
    save()
    # File-level rollback only. No block devices are written.
    command('mv ' + old + ' ' + target)
    assert command('sha256sum ' + target).split()[0] == candidate['source_sha256']
    record['state'] = 'rolled_back'
    save()
    raise
command('sync')
record.update(state='applied_and_verified', verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              bootanimation_validated=False, hardware_result='Awaiting Android boot test.')
save()
print(json.dumps(record, indent=2))
