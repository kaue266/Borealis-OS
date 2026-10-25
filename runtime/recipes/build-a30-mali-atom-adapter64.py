"""Build and emulate a bounded userspace atom ABI adapter; no device changes."""
import datetime
import hashlib
import json
import random
import struct
import subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import *

root = Path(__file__).resolve().parents[1]
base = root / 'outputs/BorealisOS-Android17/validation/imported-port-review-20261022T230200Z'
raw = json.loads((base / 'latest-recovery-gpu-review.json').read_text())['directory']
directory = Path('/mnt/' + raw[0].lower() + raw[2:].replace('\\', '/')) if raw[1:2] == ':' else Path(raw)
original_path = directory / 'libGLES_mali_64.so'
original = original_path.read_bytes()
assert hashlib.sha256(original).hexdigest() == '55dd17f913f4f478b41eb6ee1f860635127e5779a29107031faf3bbdbaee79a8'
out = base / 'mali-atom-adapter64-v1'
out.mkdir(exist_ok=True)
clang_dir = Path('/home/android/borealisos-android17/prebuilts/clang/host/linux-x86/clang-r584948b/bin')
entry, hook = 0x233ba40, 0xacd034
fd, ioctl, errno = 0xacdd58, 0x233b130, 0x233a630
subprocess.run([str(clang_dir / 'clang'), '--target=aarch64-linux-android', '-c',
                str(root / 'work/a30-mali-atom-adapter64.S'), '-o', str(out / 'adapter.o')], check=True)
subprocess.run([str(clang_dir / 'ld.lld'), '-m', 'aarch64elf', '-Ttext=' + hex(entry), '-e', 'borealis_atom_adapter',
                '--defsym=mali_get_fd=' + hex(fd), '--defsym=mali_ioctl=' + hex(ioctl), '--defsym=mali_errno=' + hex(errno),
                str(out / 'adapter.o'), '-o', str(out / 'adapter.elf')], check=True)
with (out / 'adapter.elf').open('rb') as source:
    elf = ELFFile(source)
    section = elf.get_section_by_name('.text')
    assert section['sh_addr'] == entry
    code = section.data()
assert entry + len(code) <= 0x233c000
assert original[entry:entry + len(code)] == b'\0' * len(code)
with original_path.open('rb') as source:
    elf = ELFFile(source)
    phdr = next((i, p) for i, p in enumerate(elf.iter_segments()) if p['p_type'] == 'PT_LOAD' and p['p_flags'] == 5)
    index, segment = phdr
    assert segment['p_offset'] == segment['p_vaddr'] == 0x749000
    assert segment['p_filesz'] == segment['p_memsz'] == 0x1bf2a30
    for section in elf.iter_sections():
        if section['sh_flags'] & 2:
            assert not (section['sh_addr'] < entry + len(code) and section['sh_addr'] + section['sh_size'] > entry), section.name

patched = bytearray(original)
changes = []
def patch(offset, expected, replacement, reason):
    assert patched[offset:offset + len(expected)] == expected, hex(offset)
    patched[offset:offset + len(expected)] = replacement
    changes.append(dict(offset=hex(offset), before=expected.hex(), after=replacement.hex(), reason=reason))

branch = struct.pack('<I', 0x14000000 | (((entry - hook) // 4) & 0x3ffffff))
patch(hook, bytes.fromhex('fe4fbfa9'), branch, 'Replace submit wrapper entry with the bounded real format converter.')
patch(entry, b'\0' * len(code), code, 'Adapter in unused executable segment tail padding.')
for offset, before, after, reason in [
    (0xacbcd4, '09068052', '09088052', 'Restore honest 64-byte source stride; converter submits genuine 48-byte atoms.'),
    (0xacbcf0, '1f2003d5', '00010035', 'Restore original submit failure handling.'),
    (0xaa7984, '1f2003d5', '1f050439', 'Restore completion store now that the correct userdata is transferred.'),
    (0xaa7070, '4c000014', '600e40f9', 'Restore signal completion handler.'),
    (0xaa707c, '00008052', '00013fd6', 'Restore original completion callback.'),
]:
    patch(offset, bytes.fromhex(before), bytes.fromhex(after), reason)
phoff = struct.unpack_from('<Q', original, 32)[0]
phentsize = struct.unpack_from('<H', original, 54)[0]
new_length = entry + len(code) - segment['p_vaddr']
patch(phoff + index * phentsize + 32, struct.pack('<QQ', segment['p_filesz'], segment['p_memsz']),
      struct.pack('<QQ', new_length, new_length), 'Extend existing RX segment within its final page; no new segment or RWX mapping.')
assert len(patched) == len(original)
candidate = out / 'libGLES_mali.so'
candidate.write_bytes(patched)

# Execute the actual candidate entry and adapter, intercepting only external
# libc calls. No ARM code runs on the phone in these tests.
results = []
registers = [UC_ARM64_REG_X19, UC_ARM64_REG_X20, UC_ARM64_REG_X21, UC_ARM64_REG_X22, UC_ARM64_REG_X29]
producer = json.loads((directory / 'offline-gpu-submit/atom-layout-emulation.json').read_text())['cases']
for count, stride, error in [(0, 64, 0), (1, 64, 0), (2, 64, 0), (255, 64, 0), (256, 64, 0),
                             (257, 64, 0), (0xffffffff, 64, 0), (1, 48, 0), (1, 64, 12), (2, 64, 16), (1, 64, 22)]:
    emu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for address, size in [(hook & ~4095, 8192), (entry & ~4095, 4096), (0x233a000, 8192),
                          (0x4000000, 0x20000), (0x5000000, 0x10000), (0x6000000, 0x1000)]:
        # The adapter and ioctl PLT share the same mapped final page.
        try:
            emu.mem_map(address, size)
        except Exception:
            if address != 0x233a000:
                raise
            emu.mem_map(0x233a000, 4096)
    emu.mem_write(hook, bytes(patched[hook:hook + 4]))
    emu.mem_write(entry, code)
    emu.mem_write(fd, original[fd:fd + 8])
    source, desc, context, errptr = 0x5000000, 0x5005000, 0x5006000, 0x5007000
    rng = random.Random(count + stride + error)
    raw_atoms = bytearray(rng.randbytes(min(count, 256) * 64))
    if count in (1, 2):
        raw_atoms[:64] = bytes.fromhex(producer[0]['real_binary_produced_hex'])
        if count == 2:
            raw_atoms[64:128] = bytes.fromhex(producer[1]['real_binary_produced_hex'])
    emu.mem_write(source, bytes(raw_atoms) if raw_atoms else b'\x00')
    descriptor = struct.pack('<QII', source, count, stride)
    emu.mem_write(desc, descriptor)
    # uku_get_fd is also tested by the exact instruction bytes; initialize
    # its simple context field below according to those bytes.
    assert original[fd:fd + 8].hex() == '000040b9c0035fd6'
    emu.mem_write(context, struct.pack('<I', 42))
    emu.mem_write(errptr, struct.pack('<I', error))
    emu.reg_write(UC_ARM64_REG_SP, 0x401f000)
    emu.reg_write(UC_ARM64_REG_X0, context)
    emu.reg_write(UC_ARM64_REG_X1, desc)
    emu.reg_write(UC_ARM64_REG_X30, 0x6000000)
    for i, reg in enumerate(registers):
        emu.reg_write(reg, 0x102030400 + i)
    captured = []
    def external(uc, address, size, data):
        if address == ioctl:
            assert uc.reg_read(UC_ARM64_REG_X0) == 42
            assert uc.reg_read(UC_ARM64_REG_X1) == 0x40108002
            ptr = uc.reg_read(UC_ARM64_REG_X2)
            atoms, real_count, real_stride = struct.unpack('<QII', uc.mem_read(ptr, 16))
            assert real_count == count and real_stride == 48
            packed = bytes(uc.mem_read(atoms, real_count * real_stride)) if real_count else b''
            expected = b''.join(raw_atoms[i * 64 + 8:i * 64 + 56] for i in range(count))
            assert packed == expected
            captured.append(dict(count=real_count, stride=real_stride, bytes=len(packed)))
            uc.reg_write(UC_ARM64_REG_X0, 0xffffffffffffffff if error else 0)
            uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))
        elif address == errno:
            uc.reg_write(UC_ARM64_REG_X0, errptr)
            uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))
    emu.hook_add(UC_HOOK_CODE, external)
    emu.emu_start(hook, 0x6000000, count=10000)
    expected_return = 3 if count > 256 or stride != 64 else (2 if error == 12 else 63 if error == 16 else 3 if error else 0)
    assert emu.reg_read(UC_ARM64_REG_X0) == expected_return
    assert emu.reg_read(UC_ARM64_REG_SP) == 0x401f000
    for i, reg in enumerate(registers):
        assert emu.reg_read(reg) == 0x102030400 + i
    assert bytes(emu.mem_read(desc, 16)) == descriptor
    assert bytes(emu.mem_read(source, len(raw_atoms))) == raw_atoms if raw_atoms else True
    assert bool(captured) == (count <= 256 and stride == 64)
    results.append(dict(count=count, source_stride=stride, errno=error, result=expected_return, ioctl=captured, passed=True))

record = dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), directory=str(out),
              source_sha256=hashlib.sha256(original).hexdigest(), candidate_sha256=hashlib.sha256(patched).hexdigest(),
              file_bytes=len(patched), adapter_bytes=len(code), adapter_va=hex(entry), hook_va=hex(hook),
              changes=changes, emulation_tests=results, all_tests_passed=True,
              layout_conversion='For each 64-byte atom, copy bytes 8..55 into a separate 48-byte atom; skip seq_nr and modern tail.',
              completion_event_bytes=24, completion_events_modified=False, original_source_and_descriptor_preserved=True,
              stack_bound_bytes=64 + 16 + 256 * 48, phone_changes=False, kernel_or_rom_compilation=False,
              limitations=['GPU hardware validation pending.', '32-bit Mali library still has the previous incorrect size-only patch.',
                           'Newer nonzero renderpass/JIT features are not implemented by this adapter.'])
(out / 'candidate.json').write_text(json.dumps(record, indent=2) + '\n')
(base / 'latest-mali-atom-adapter64.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k:record[k] for k in ('directory', 'candidate_sha256', 'adapter_bytes', 'all_tests_passed', 'stack_bound_bytes', 'phone_changes')}, indent=2))
