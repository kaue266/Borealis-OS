"""Apply file-level repairs backed by the collected Android crashes."""
import datetime
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/BorealisOS-Android17/validation/imported-port-review-20261022T230200Z'
OUT = Path(json.loads((BASE / 'latest-connectivity-crashes.json').read_text())['directory'])
BACKUP = Path(json.loads((OUT / 'efs-review.json').read_text())['efs_image_backup']).parent
ADB = [r'F:\platform-tools\adb.exe', '-s', 'DEVICE_SERIAL']
sha = lambda data: hashlib.sha256(data).hexdigest()
def run(*args, required=True, timeout=40):
    p = subprocess.run(ADB + list(args), capture_output=True, timeout=timeout)
    if required and p.returncode:
        raise RuntimeError((args, p.stdout[-800:], p.stderr[-800:]))
    return p
def shell(command, **kwargs):
    return run('shell', command, **kwargs)

assert run('get-state').stdout.strip() == b'recovery'
assert not shell('pidof system_server surfaceflinger zygote zygote64; true').stdout.strip()
assert json.loads((OUT / 'efs-review.json').read_text())['factory_bt_address_valid_format_unicast_nonzero']
mounts = shell('cat /proc/mounts').stdout
mounted = []
changed = []
originals = {}
script = r'''#!/system/bin/sh
# Explicit legacy diagnostic mode: DNS stall detection remains enabled.
# TCP socket polling currently crashes NetworkStack on absent BPF maps.
# This does not provide BPF support, alter firewall policy, or fake validation.
umask 077
base=/data/debug/borealis-connectivity
mkdir -p "$base"
id=$(cat /proc/sys/kernel/random/boot_id)
dir="$base/$id"
mkdir -p "$dir"
exec > "$dir/actions.txt" 2>&1
date
cat /proc/uptime
if [ ! -f "$base/data-stall-original.txt" ]; then
    /system/bin/device_config get connectivity data_stall_evaluation_type > "$base/data-stall-original.txt"
fi
/system/bin/device_config put connectivity data_stall_evaluation_type 1
echo "device_config_put_exit=$?"
/system/bin/device_config get connectivity data_stall_evaluation_type
logcat -b all -v threadtime -f "$dir/logcat.txt" -r 1024 -n 3 &
logger=$!
trap 'kill "$logger" 2>/dev/null' EXIT HUP INT TERM
i=0
while [ "$i" -lt 18 ]; do
    date >> "$dir/processes.txt"
    cat /proc/uptime >> "$dir/processes.txt"
    for p in sys.boot_completed init.svc.adbd init.svc.netd init.svc.zygote init.svc.zygote_secondary init.svc.bootanim; do
        printf '%s=' "$p" >> "$dir/processes.txt"
        getprop "$p" >> "$dir/processes.txt"
    done
    for n in system_server surfaceflinger adbd netd com.android.networkstack.process com.android.bluetooth; do
        printf '%s=' "$n" >> "$dir/processes.txt"
        pidof "$n" >> "$dir/processes.txt"
    done
    if [ "$i" -eq 0 ] || [ "$i" -eq 6 ] || [ "$i" -eq 17 ]; then
        {
            date
            cat /proc/mounts | grep /mnt/vendor/efs
            cmd wifi status
            ip addr show wlan0
            ip route
            timeout 10 dumpsys connectivity
            timeout 10 dumpsys bluetooth_manager
            timeout 10 dumpsys activity lastanr
            dmesg | tail -n 1800
        } > "$dir/state-$i.txt" 2>&1
    fi
    i=$((i+1))
    sleep 10
done
'''
rc = '''service borealis-connectivity-diagnostics /system/bin/sh /system/etc/borealis-connectivity-diagnostics.sh
    class late_start
    user root
    group root system shell log inet net_admin bluetooth
    seclabel u:r:su:s0
    disabled
    oneshot

on property:sys.boot_completed=1 && property:ro.debuggable=1
    start borealis-connectivity-diagnostics
'''
try:
    for point, part in [('/system_root', 'system'), ('/vendor', 'vendor')]:
        if not any(line.split()[1] == point.encode() for line in mounts.splitlines()):
            shell(f'mount -t ext4 -o ro /dev/block/platform/13500000.dwmmc0/by-name/{part} {point}')
            mounted.append(point)
    assert shell('sha256sum /system_root/system/bin/init').stdout.decode().split()[0] == 'bccb396f51e5e6dd24f75b26858e3ce63f89a4e38e14bdcdb9fc6aaf946bf21f'
    assert shell('test -x /system_root/system/bin/device_config').returncode == 0
    init_path = '/system_root/system/etc/init/hw/init.rc'
    vendor_path = '/vendor/etc/init/hw/init.exynos7904.rc'
    init = run('exec-out', 'cat', init_path).stdout
    vendor = run('exec-out', 'cat', vendor_path).stdout
    assert sha(init) == 'e22a7507064783be046103b3add3283d8a9d2a93868cdafa7e51d5a0215d5b11'
    assert vendor == (OUT / 'installed/vendor/etc/init/hw/init.exynos7904.rc').read_bytes()
    early = b'on init && property:ro.debuggable=1\n    setprop sys.usb.config adb\n    start adbd\n    start console\n'
    late = b'# Start adbd at boot after the vendor FunctionFS mount, not in early init.\non init && property:ro.debuggable=1\n    start console\n'
    assert init.count(early) == 1
    init_after = init.replace(early, late)
    assert b'    mount none /data/data /data_mirror/data_ce/null/0 bind\n' in init_after
    assert b'on boot && property:ro.debuggable=1\n    setprop sys.usb.config adb\n    restart adbd\n' in init_after
    line_end = b'\r\n' if b'\r\n' in vendor else b'\n'
    old = b'on fs' + line_end + b'    mount_all /vendor/etc/fstab.${ro.hardware} --early' + line_end
    new = line_end.join([b'on fs', b'    # Prepare the actual factory EFS mount target immediately before mount_all.',
                         b'    mkdir /mnt/vendor 0755 root root', b'    mkdir /mnt/vendor/efs 0771 radio system',
                         b'    mount_all /vendor/etc/fstab.${ro.hardware} --early', b''])
    assert vendor.count(old) == 1
    vendor_after = vendor.replace(old, new)
    specs = [(init_path, init, init_after, '644'), (vendor_path, vendor, vendor_after, '644'),
             ('/system_root/system/etc/borealis-connectivity-diagnostics.sh', None, script.encode(), '755'),
             ('/system_root/system/etc/init/borealis-connectivity-diagnostics.rc', None, rc.encode(), '644')]
    for i, (path, before, after, mode) in enumerate(specs):
        if before is None:
            assert shell('test ! -e ' + path).returncode == 0
        else:
            meta = shell('stat -c %a:%u:%g:%i ' + path).stdout.decode().strip()
            originals[path] = (before, meta)
            (OUT / (f'file-{i}.before')).write_bytes(before)
            (BACKUP / (f'file-{i}.before')).write_bytes(before)
        local = OUT / (f'file-{i}.after')
        local.write_bytes(after)
        shutil.copy2(local, BACKUP / local.name)
        run('push', str(local), f'/tmp/borealis-connectivity-{i}')
        assert shell(f'sha256sum /tmp/borealis-connectivity-{i}').stdout.decode().split()[0] == sha(after)
    # No persistent modifications happen until every candidate and backup is ready.
    shell('mount -o remount,rw /system_root')
    shell('mount -o remount,rw /vendor')
    try:
        for i, (path, before, after, mode) in enumerate(specs):
            changed.append((i, path, before))
            shell(f'cat /tmp/borealis-connectivity-{i} > ' + path)
            if before is None:
                shell('chmod ' + mode + ' ' + path)
                shell('chown 0:0 ' + path)
                shell('chcon u:object_r:system_file:s0 ' + path)
            assert run('exec-out', 'cat', path).stdout == after
            if before is not None:
                assert shell('stat -c %a:%u:%g:%i ' + path).stdout.decode().strip() == originals[path][1]
    except BaseException:
        for i, path, before in reversed(changed):
            if before is None:
                shell('rm ' + path)
            else:
                run('push', str(OUT / f'file-{i}.before'), f'/tmp/borealis-connectivity-{i}-rollback')
                shell(f'cat /tmp/borealis-connectivity-{i}-rollback > ' + path)
                assert run('exec-out', 'cat', path).stdout == before
        raise
    finally:
        shell('sync')
        shell('mount -o remount,ro /vendor')
        shell('mount -o remount,ro /system_root')
    record = {'state': 'applied_readback_verified_runtime_pending', 'directory': str(OUT),
              'applied_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'changes': [{'path': path, 'before_sha256': sha(before) if before is not None else None,
                           'after_sha256': sha(after)} for path, before, after, mode in specs],
              'efs_contents_not_modified': True, 'efs_backup': str(BACKUP / 'efs-before-mountpoint-repair.img'),
              'wifi_mode': 'data_stall_evaluation_type=1 (DNS-only optional stall detection); to be applied by device_config after boot',
              'wifi_validation_untouched': True, 'bpf_support_claimed': False,
              'new_usb_hal_installed': False, 'kernel_changed': False,
              'rollback': 'Restore file-0.before and file-1.before to the recorded paths; remove the two new diagnostics files. Restore DeviceConfig from /data/debug/borealis-connectivity/data-stall-original.txt using device_config put, or delete if null.'}
    (OUT / 'application.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    (BASE / 'latest-connectivity-repairs.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    shutil.copy2(OUT / 'application.json', BACKUP / 'application.json')
    print(json.dumps(record, indent=2))
finally:
    for point in reversed(mounted):
        shell('umount ' + point)
