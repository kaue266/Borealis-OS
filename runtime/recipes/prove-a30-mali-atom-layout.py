"""Execute the real atom-producer bytes in Unicorn and compare exact kernel field reads."""
import hashlib
import json
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import UC_ARM64_REG_SP, UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3, UC_ARM64_REG_X4, UC_ARM64_REG_X5

root = Path(__file__).resolve().parents[1]
base = root / 'outputs/BorealisOS-Android17/validation/imported-port-review-20261022T230200Z'
record = json.loads((base / 'latest-recovery-gpu-review.json').read_text(encoding='utf-8'))
directory = record['directory']
directory = Path('/mnt/' + directory[0].lower() + directory[2:].replace('\\', '/')) if directory[1:2] == ':' else Path(directory)
binary = (directory / 'libGLES_mali_64.so').read_bytes()
assert hashlib.sha256(binary).hexdigest() == record['installed_mali_patch_comparison']['libGLES_mali_64.so']['sha256']
start, stop = 0xaa6360, 0xaa63f8
assert binary[start:start + 4] == bytes.fromhex('fe57bea9')
emu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
emu.mem_map(0xaa6000, 0x1000)
emu.mem_write(0xaa6000, binary[0xaa6000:0xaa7000])
emu.mem_map(0x2000000, 0x10000)
emu.mem_map(0x4000000, 0x10000)
context, info, ids, deps, atoms = 0x2000000, 0x2001000, 0x2002000, 0x2003000, 0x2004000
emu.mem_write(info, struct.pack('<Q', atoms))
emu.mem_write(context + 8, struct.pack('<Q', 0x2005000))
emu.mem_write(ids, bytes([0x36, 0x37, 0x38, 0x39]))
cases = []
for index in (1, 2):
    emu.mem_write(deps, bytes([5, 1, 7, 2]))
    for reg, value in [(UC_ARM64_REG_SP, 0x400f000), (UC_ARM64_REG_X0, context),
                       (UC_ARM64_REG_X1, index), (UC_ARM64_REG_X2, info), (UC_ARM64_REG_X3, ids),
                       (UC_ARM64_REG_X4, deps), (UC_ARM64_REG_X5, 0xaabbccdd01234567)]:
        emu.reg_write(reg, value)
    emu.emu_start(start, stop, count=100)
    atom = bytes(emu.mem_read(atoms + (index - 1) * 64, 64))
    case = dict(index=index - 1, real_binary_produced_hex=atom.hex(),
                producer_atom_number=atom[0x30], kernel_4_4_reads_atom_number=atom[0x28],
                producer_dependencies=atom[0x2c:0x30].hex(), kernel_4_4_reads_dependencies=atom[0x24:0x28].hex(),
                producer_core_req=hex(struct.unpack_from('<I', atom, 0x34)[0]),
                kernel_4_4_reads_core_req=hex(struct.unpack_from('<I', atom, 0x2c)[0]))
    assert case['producer_atom_number'] == 0x36 + index
    assert case['kernel_4_4_reads_atom_number'] == 0
    assert case['producer_dependencies'] == '05010702'
    assert case['kernel_4_4_reads_dependencies'] == '00000000'
    assert case['producer_core_req'] == '0x221'
    assert case['kernel_4_4_reads_core_req'] == '0x2070105'
    cases.append(case)
actual_second = bytes(emu.mem_read(atoms + 64, 64))
legacy_second = bytes(emu.mem_read(atoms + 48, 48))
assert legacy_second != actual_second[:48]
result = dict(passed=True, cases=cases, real_function='cmarp_create_profiling_atom',
              executed_range=[hex(start), hex(stop)], external_calls_executed=False,
              binary_sha256=hashlib.sha256(binary).hexdigest(),
              producer_stride=64, ioctl_declared_stride_after_existing_patch=48, kernel_required_stride=48,
              second_atom_pointer_delta=16,
              finding='Existing patch changes the declared size only. Real producer atom IDs, dependencies and core_req do not match the installed kernel field offsets, even for one atom.',
              limitations=['This exercises the exact profiling-atom producer, not every producer.',
                           'It proves an ABI mismatch; it does not validate a replacement converter or GPU hardware.',
                           'Other existing callback patches and event ABI still require review.'],
              phone_execution=False, phone_changes=False, kernel_or_rom_compilation=False)
path = directory / 'offline-gpu-submit/atom-layout-emulation.json'
path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
