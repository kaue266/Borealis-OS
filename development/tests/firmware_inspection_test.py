#!/usr/bin/env python3
"""Regression proof for inspection of future images, using explicit fixtures."""
from pathlib import Path
import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
import zipfile

package = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('borealis_inspection', package / 'tools/inspect-firmware.py')
inspection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspection)


class InspectionTest(unittest.TestCase):
    def setUp(self):
        self.props = {'ro.build.version.sdk': '37', 'ro.build.version.release': '17',
                      'ro.borealis.device': 'a30', 'ro.borealis.root': 'optional',
                      'ro.build.fingerprint': 'borealis/a30/a30:17/FIXTURE/1:userdebug/test-keys'}
        self.metadata = {'pre-device': 'a30,a30dd', 'ota-type': 'BLOCK',
                         'post-build': self.props['ro.build.fingerprint']}
        self.kernel = b'fixture-kernel-for-parser-tests'
        self.dtb = b'fixture-dtb'
        self.expected = {'image_bytes': len(self.kernel), 'root_enabled': False,
                         'sha256': hashlib.sha256(self.kernel).hexdigest()}
        self.dtb_expected = {'sha256': hashlib.sha256(self.dtb).hexdigest()}

    def test_android17_identity(self):
        inspection.validate_identity(self.props, self.metadata)

    def test_android13_or17_label_alone_is_rejected(self):
        self.props['ro.build.version.sdk'] = '33'
        with self.assertRaises(ValueError):
            inspection.validate_identity(self.props, self.metadata)

    def test_wrong_device_and_mismatched_ota_rejected(self):
        for key, value in [('pre-device', 'a50'), ('post-build', 'other-build'), ('ota-type', 'AB')]:
            metadata = {**self.metadata, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                inspection.validate_identity(self.props, metadata)

    def test_conflicting_properties_rejected(self):
        with self.assertRaises(ValueError):
            inspection.properties(b'ro.build.version.sdk=37\nro.build.version.sdk=33\n')

    def test_legacy_boot_kernel_and_commandline_extracted(self):
        header = bytearray(2048)
        header[:8] = b'ANDROID!'
        struct.pack_into('<I', header, 8, len(self.kernel))
        struct.pack_into('<I', header, 36, 2048)
        header[64:64 + 13] = b'fixture=value'
        kernel, version, commandline = inspection.kernel_from_boot(header + self.kernel)
        self.assertEqual((kernel, version, commandline), (self.kernel, 0, 'fixture=value'))

    def test_invalid_page_or_truncated_kernel_rejected(self):
        header = bytearray(2048)
        header[:8] = b'ANDROID!'
        struct.pack_into('<I', header, 8, len(self.kernel))
        for page in (3000, 2048):
            struct.pack_into('<I', header, 36, page)
            with self.subTest(page=page), self.assertRaises(ValueError):
                inspection.kernel_from_boot(header)

    def test_main_kernel_with_optional_dtb(self):
        inspection.verify_kernel(self.kernel, self.expected, self.dtb_expected)
        result = inspection.verify_kernel(self.kernel + self.dtb, self.expected, self.dtb_expected)
        self.assertTrue(result['appended_dtb'])

    def test_root_different_kernel_and_unknown_suffix_rejected(self):
        for kernel, expected in [(b'other-kernel', self.expected),
                                 (self.kernel, {**self.expected, 'root_enabled': True}),
                                 (self.kernel + b'unknown', self.expected)]:
            with self.subTest(kernel=kernel, expected=expected), self.assertRaises(ValueError):
                inspection.verify_kernel(kernel, expected, self.dtb_expected)

    def fixture_archives(self, directory, system_image=b'fixture-system', ota_image_overrides=None):
        target, ota = Path(directory) / 'target.zip', Path(directory) / 'ota.zip'
        header = bytearray(2048)
        header[:8] = b'ANDROID!'
        struct.pack_into('<I', header, 8, len(self.kernel))
        struct.pack_into('<I', header, 36, 2048)
        lines = lambda values: '\n'.join(key + '=' + str(value) for key, value in values.items()) + '\n'
        with zipfile.ZipFile(target, 'w') as archive:
            archive.writestr('SYSTEM/etc/build.prop', lines(self.props))
            archive.writestr('META/misc_info.txt', lines({'boot_size': 8192, 'system_size': 1024}))
            archive.writestr('IMAGES/boot.img', header + self.kernel)
            archive.writestr('IMAGES/system.img', system_image)
            archive.writestr('IMAGES/dtbo.img', self.dtb)
            archive.writestr('RADIO/dtb.img', self.dtb)
        with zipfile.ZipFile(ota, 'w') as archive:
            archive.writestr('META-INF/com/android/metadata', lines(self.metadata))
            images = {'boot.img': header + self.kernel, 'dtb.img': self.dtb, 'dtbo.img': self.dtb}
            images.update(ota_image_overrides or {})
            for name, content in images.items():
                archive.writestr(name, content)
        pair = {'artifacts': {'main': self.expected, 'dtb.img': self.dtb_expected, 'dtbo.img': self.dtb_expected}}
        physical = {'scope': 'synthetic fixture capacities', 'reported_device': 'a30', 'installed_sdk': 33,
                    'partitions': {'boot': {'capacity_bytes': 8192}, 'system': {'capacity_bytes': 1024},
                                   'dtbo': {'capacity_bytes': 1024}}}
        return target, ota, pair, physical

    def test_structural_inspection_never_means_release_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            report = inspection.inspect(*self.fixture_archives(directory))
        self.assertTrue(report['structural_checks_passed'])
        self.assertFalse(report['release_validated'])
        self.assertFalse(report['installable_package'])
        self.assertFalse(report['flash_performed'])
        self.assertTrue(report['ota_images_match_target_files'])

    def test_stale_ota_images_are_rejected_even_with_valid_crc(self):
        for image in ('boot.img', 'dtb.img', 'dtbo.img'):
            with self.subTest(image=image), tempfile.TemporaryDirectory() as directory:
                arguments = self.fixture_archives(directory, ota_image_overrides={image: b'stale-image'})
                with self.assertRaisesRegex(ValueError, 'OTA image differs from target-files'):
                    inspection.inspect(*arguments)

    def test_sparse_logical_size_and_physical_capacity_are_enforced(self):
        sparse = struct.pack('<IHHHHIIII', 0xED26FF3A, 1, 0, 28, 12, 4096, 2, 1, 0)
        with tempfile.TemporaryDirectory() as directory:
            arguments = list(self.fixture_archives(directory, sparse))
            with self.assertRaisesRegex(ValueError, 'exceeds declared partition'):
                inspection.inspect(*arguments)
            arguments = list(self.fixture_archives(directory))
            arguments[3]['partitions']['system']['capacity_bytes'] = 1
            with self.assertRaisesRegex(ValueError, 'physical partition'):
                inspection.inspect(*arguments)

    def test_archive_crc_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            arguments = self.fixture_archives(directory)
            target = arguments[0]
            target.write_bytes(target.read_bytes().replace(b'fixture-system', b'broken--system'))
            with self.assertRaisesRegex(ValueError, 'ZIP CRC failure'):
                inspection.inspect(*arguments)

    def test_known_google_service_fixture_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            arguments = self.fixture_archives(directory)
            with zipfile.ZipFile(arguments[0], 'a') as archive:
                archive.writestr('PRODUCT/priv-app/GmsCore/GmsCore.apk', b'fixture')
            with self.assertRaisesRegex(ValueError, 'Google service'):
                inspection.inspect(*arguments)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(InspectionTest))
    (package / 'validation/firmware-inspector-tests.json').write_text(json.dumps({
        'scope': 'Inspector regression tests using synthetic fixtures; no firmware image proof',
        'cases': result.testsRun, 'passed': result.wasSuccessful(), 'device_tested': False}, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
