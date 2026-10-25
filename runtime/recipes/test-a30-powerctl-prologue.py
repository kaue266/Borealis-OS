import json,struct
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM
import unicorn.arm64_const as reg
root=Path(__file__).resolve().parents[1];base=root/'outputs/BorealisOS-Android17/validation/imported-port-review-20261022T230200Z'
out=Path(json.loads((base/'latest-controls-recovery-files.json').read_text())['directory']);raw=(out/'init-powerctl-restored').read_bytes()
proof=[]
for seed in [0,0x12345678,0xabcdef123456]:
 uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM);uc.mem_map(0x100000,4096);uc.mem_write(0x100000,raw[0xf8050:0xf806c]);uc.mem_map(0x400000,0x3000)
 sp=0x401800;uc.mem_write(sp,b'Z'*256);uc.reg_write(reg.UC_ARM64_REG_SP,sp)
 values={i:seed+i for i in range(19,31)}
 for i,value in values.items():uc.reg_write(getattr(reg,'UC_ARM64_REG_X'+str(i)),value)
 uc.emu_start(0x100000,0x10001c)
 saved=list(struct.unpack('<12Q',bytes(uc.mem_read(sp-96,96))))
 order=[29,30,28,27,26,25,24,23,22,21,20,19]
 assert saved==[values[i] for i in order]
 assert uc.reg_read(reg.UC_ARM64_REG_SP)==sp-96 and uc.reg_read(reg.UC_ARM64_REG_X29)==sp-96
 assert bytes(uc.mem_read(sp,256))==b'Z'*256
 proof.append({'seed':hex(seed),'six_register_pairs_saved':True,'stack_frame_bytes':96,'caller_stack_untouched':True})
(out/'powerctl-prologue-tests.json').write_text(json.dumps({'tests':proof,'all_passed':True,'scope':'Actual 28 bytes from candidate ELF, not full reboot routine'},indent=2)+'\n')
print('3 actual-byte prologue tests passed; 96-byte frame, saved registers and caller stack verified.')
