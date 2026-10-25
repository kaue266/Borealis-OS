#!/usr/bin/env python3
"""Inspect actual target-files/OTA output. This is not release or boot approval."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import zipfile


def properties(data):
    result = {}
    for line in data.decode('utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            if key in result and result[key] != value:
                raise ValueError('Conflicting property ' + key)
            result[key] = value
    return result


def kernel_from_boot(data):
    if len(data) < 44 or data[:8] != b'ANDROID!':
        raise ValueError('Not an Android boot image')
    size = struct.unpack_from('<I', data, 8)[0]
    version = struct.unpack_from('<I', data, 40)[0]
    if version in (0, 1, 2):
        page = struct.unpack_from('<I', data, 36)[0]
        if page < 2048 or page > 65536 or page & (page - 1):
            raise ValueError('Invalid legacy boot page size')
        if len(data) < 1632:
            raise ValueError('Truncated legacy boot header')
        command_line = b' '.join(part.split(b'\0', 1)[0] for part in (data[64:576], data[608:1632]))
    elif version in (3, 4):
        page = 4096
        if len(data) < 1580:
            raise ValueError('Truncated modern boot header')
        command_line = data[44:1580].split(b'\0', 1)[0]
    else:
        raise ValueError(f'Unsupported boot header version {version}')
    if not size or page + size > len(data):
        raise ValueError('Truncated or empty boot kernel')
    return data[page:page + size], version, command_line.decode('ascii', errors='replace').strip()


def build_fingerprint(props):
    values = {props[key] for key in ('ro.build.fingerprint', 'ro.system.build.fingerprint')
              if props.get(key)}
    if len(values) != 1:
        raise ValueError('Missing or conflicting system build fingerprints')
    return next(iter(values))


def validate_identity(props, metadata):
    if props.get('ro.build.version.sdk') != '37':
        raise ValueError('System is not Android 17 / SDK 37')
    if props.get('ro.build.version.release') != '17':
        raise ValueError('Android release is not 17')
    if props.get('ro.borealis.device') != 'a30':
        raise ValueError('Missing Borealis A30 identity')
    if props.get('ro.borealis.root') != 'optional':
        raise ValueError('Unexpected root product contract')
    if 'a30' not in metadata.get('pre-device', '').split(','):
        raise ValueError('OTA does not target a30')
    if metadata.get('ota-type') != 'BLOCK':
        raise ValueError('Unexpected OTA partition scheme for original A30')
    fingerprint = build_fingerprint(props)
    if metadata.get('post-build') != fingerprint:
        raise ValueError('OTA and target-files fingerprints differ')


def verify_kernel(kernel, expected, dtb):
    image_size = expected['image_bytes']
    digest = hashlib.sha256(kernel[:image_size]).hexdigest()
    if len(kernel) < image_size or digest != expected['sha256'] or expected['root_enabled']:
        raise ValueError('Boot image does not contain the inspected kernel without KernelSU')
    trailing = kernel[image_size:]
    if trailing and hashlib.sha256(trailing).hexdigest() != dtb['sha256']:
        raise ValueError('Unexpected data appended to the boot kernel')
    return {'image_sha256': digest, 'kernel_bytes': len(kernel),
            'appended_dtb': bool(trailing), 'root_enabled': False}


def verify_ota_image(target, ota, target_name, ota_name):
    target_bytes = target.read(target_name)
    ota_bytes = ota.read(ota_name)
    if target_bytes != ota_bytes:
        raise ValueError('OTA image differs from target-files: ' + ota_name)
    return hashlib.sha256(ota_bytes).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inspect(target, ota, pair, physical):
    checks = []
    with zipfile.ZipFile(target) as archive, zipfile.ZipFile(ota) as update:
        for opened in (archive, update):
            names = opened.namelist()
            if len(names) != len(set(names)):
                raise ValueError('Duplicate entries in ' + str(opened.filename))
            bad = opened.testzip()
            if bad:
                raise ValueError('ZIP CRC failure: ' + bad)
        checks.append('All target-files and OTA entries pass ZIP CRC verification')
        ota_image_hashes = {
            image: verify_ota_image(archive, update, target_name, image)
            for target_name, image in (('IMAGES/boot.img', 'boot.img'),
                                       ('RADIO/dtb.img', 'dtb.img'),
                                       ('IMAGES/dtbo.img', 'dtbo.img'))
        }
        checks.append('OTA boot, DTB and DTBO bytes match the inspected target-files images')
        prop_name = next((name for name in ('SYSTEM/etc/build.prop', 'SYSTEM/build.prop')
                          if name in archive.namelist()), None)
        if not prop_name:
            raise ValueError('System build properties are missing')
        props = properties(archive.read(prop_name))
        metadata = properties(update.read('META-INF/com/android/metadata'))
        validate_identity(props, metadata)
        checks.append('SDK 37, release 17, A30 product and OTA identity agree')
        misc = properties(archive.read('META/misc_info.txt'))
        partitions = {}
        for partition in ('boot', 'recovery', 'system', 'vendor', 'product', 'system_ext'):
            name = 'IMAGES/' + partition + '.img'
            if name not in archive.namelist():
                continue
            size = archive.getinfo(name).file_size
            limit = misc.get(partition + '_size')
            # Sparse images require the unsparse size, not their zip-entry size.
            with archive.open(name) as stream:
                header = stream.read(28)
            sparse = len(header) >= 28 and struct.unpack_from('<I', header)[0] == 0xED26FF3A
            logical = (struct.unpack_from('<I', header, 12)[0] * struct.unpack_from('<I', header, 16)[0]
                       if sparse else size)
            if limit and logical > int(limit):
                raise ValueError(partition + ': image exceeds declared partition')
            actual = physical['partitions'].get(partition, {}).get('capacity_bytes')
            if actual and logical > actual:
                raise ValueError(partition + ': image exceeds the connected A30 physical partition')
            partitions[partition] = {'stored_bytes': size, 'logical_bytes': logical,
                                     'declared_limit_bytes': int(limit) if limit else None,
                                     'physical_capacity_bytes': actual}
        boot = archive.read('IMAGES/boot.img')
        kernel, header_version, command_line = kernel_from_boot(boot)
        kernel_report = verify_kernel(kernel, pair['artifacts']['main'], pair['artifacts']['dtb.img'])
        if 'selinux=permissive' in command_line or 'selinux=disabled' in command_line:
            raise ValueError('Boot command line weakens SELinux')
        checks.append('Boot carries the inspected kernel without KernelSU and no permissive command line')
        dtbo_name = 'IMAGES/dtbo.img'
        if dtbo_name not in archive.namelist():
            raise ValueError('A30 DTBO image is missing')
        dtbo_digest = hashlib.sha256(archive.read(dtbo_name)).hexdigest()
        if dtbo_digest != pair['artifacts']['dtbo.img']['sha256']:
            raise ValueError('DTBO differs from the inspected A30 image')
        if archive.getinfo(dtbo_name).file_size > physical['partitions']['dtbo']['capacity_bytes']:
            raise ValueError('DTBO exceeds the connected A30 partition')
        checks.append('DTBO matches the inspected A30 prebuilt')
        google_names = {'gmscore.apk', 'prebuiltgmscore.apk', 'phonesky.apk',
                        'googleservicesframework.apk', 'googlepartnersetup.apk',
                        'googleonetimeinitializer.apk', 'velvet.apk'}
        google_entries = [name for name in archive.namelist()
                          if Path(name).name.lower() in google_names]
        if google_entries:
            raise ValueError('Unexpected Google service files: ' + ', '.join(google_entries))
        checks.append('Known Google service APK filenames absent; APK manifest audit still required')
    return {'scope': 'Diagnostic firmware structure and correspondence to inspected source artifacts',
            'structural_checks_passed': True, 'checks': checks,
            'target_files': {'path': str(target), 'sha256': sha256_file(target)},
            'ota': {'path': str(ota), 'sha256': sha256_file(ota)},
            'ota_images_match_target_files': True, 'ota_image_sha256': ota_image_hashes,
            'build': {**{key: props.get(key) for key in ('ro.build.version.sdk', 'ro.build.version.release',
                      'ro.build.version.security_patch', 'ro.borealis.version')},
                      'fingerprint': build_fingerprint(props),
                      'fingerprint_property': 'ro.build.fingerprint' if props.get('ro.build.fingerprint')
                                              else 'ro.system.build.fingerprint'},
            'boot': {**kernel_report, 'header_version': header_version, 'command_line': command_line},
            'partitions': partitions, 'dtbo_sha256': dtbo_digest,
            'capacity_evidence': {'scope': physical['scope'], 'reported_device': physical['reported_device'],
                                  'installed_sdk': physical['installed_sdk']},
            'release_validated': False, 'installable_package': False, 'flash_performed': False,
            'pending': ['Android 17 BPF/network compatibility', 'VINTF and compiled SELinux policy',
                        'APK manifests, signatures and Android 13 Settings migration',
                        'Native visual, accessibility and graphics runtime tests',
                        'Physical hardware, normal boot, reboot and cold boot tests',
                        'Performance, temperature and battery measurements',
                        'Matching optional KernelSU installer validation']}


def main():
    package = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument('--product', type=Path, default=Path('/home/android/borealisos-android17/out/target/product/a30'))
    args = parser.parse_args()
    target_directory = args.product / 'obj/PACKAGING/target_files_intermediates'
    # This product's build rules generate canonical names. Also accept the
    # historical stamped names, but reject ambiguous sets instead of guessing.
    target_files = sorted(set(target_directory.glob('borealis_a30-target_files-*.zip')) |
                          {path for path in (target_directory / 'borealis_a30-target_files.zip',)
                           if path.is_file()})
    ota_files = sorted(set(args.product.glob('borealis_a30-ota-*.zip')) |
                       {path for path in (args.product / 'borealis_a30-ota.zip',)
                        if path.is_file()})
    output = package / 'validation/firmware-inspection.json'
    try:
        if len(target_files) != 1 or len(ota_files) != 1:
            raise ValueError(f'Expected one A30 target-files and OTA; found {len(target_files)} and {len(ota_files)}')
        pair = json.loads((package / 'validation/kernel/compiled-pair.json').read_text())
        physical = json.loads((package / 'validation/device-partitions.json').read_text())
        if physical['reported_device'] not in ('a30', 'a30dd') or physical['partition_writes_performed']:
            raise ValueError('Missing read-only A30 partition capacity evidence')
        report = inspect(target_files[0], ota_files[0], pair, physical)
    except Exception as error:
        output.write_text(json.dumps({'structural_checks_passed': False, 'error': str(error),
                          'release_validated': False, 'installable_package': False,
                          'flash_performed': False}, indent=2) + '\n')
        raise SystemExit(str(error))
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Diagnostic firmware inspected and SHA-256 recorded; Android 17 boot/release validation pending.')


if __name__ == '__main__':
    main()
