#!/usr/bin/env python3
"""Install only verified native resources between build stages; never flash."""
from pathlib import Path
import hashlib
import json
import subprocess

package = Path(__file__).resolve().parent.parent
root = Path('/home/android/borealisos-android17')
report = json.loads((package / 'validation/systemui-resource-tests.json').read_text())
assert report['passed']
assert (root / 'build/release/release_configs/cp2a.textproto').is_file()
assert subprocess.run(['pgrep', '-x', 'soong_build'], capture_output=True).returncode == 1, 'Active Soong analysis; install between stages'
prefix = Path('vendor/borealis/overlay/base/frameworks/base/packages/SystemUI/res')
changed = []
prepared = []
for name, digest in report['file_sha256'].items():
    relative = Path(name)
    assert relative.is_relative_to(prefix) and '..' not in relative.parts
    source = package / 'project' / relative
    data = source.read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest, f'{name}: resources changed after verification'
    destination = root / relative
    assert destination.resolve().is_relative_to(root.resolve())
    prepared.append((name, destination, data))
for name, destination, data in prepared:
    if not destination.is_file() or destination.read_bytes() != data:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        changed.append(name)
(package / 'validation/systemui-resource-install.json').write_text(json.dumps({
    'installed_files': report['file_sha256'], 'changed_files': changed,
    'native_apk_linked': False, 'device_tested': False, 'flash_performed': False}, indent=2) + '\n')
print(f'Installed {len(changed)} verified SystemUI resource changes; native build pending.')
