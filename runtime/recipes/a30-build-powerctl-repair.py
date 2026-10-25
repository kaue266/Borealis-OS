import hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'outputs/BorealisOS-Android17/validation/imported-port-review-20261022T230200Z'
info=json.loads((base/'latest-controls-recovery-files.json').read_text());out=Path(info['directory']);r=Path('/home/android/borealisos-android17')
current=out/'files/system_root/system/bin/init';data=current.read_bytes();offset=0xf8050
assert data[offset:offset+4]==bytes.fromhex('c0035fd6')
original=r/'out/target/product/a30/system/bin/init';raw=original.read_bytes()
signature=data[offset+4:offset+0x30]
matches=[];start=0
while True:
 at=raw.find(signature,start)
 if at<0:break
 matches.append(at);start=at+1
assert len(matches)==1,matches
original_offset=matches[0]-4;prologue=raw[original_offset:original_offset+4]
# The mapped function saves 6 register pairs; its first STP must allocate 96 bytes.
assert prologue==bytes.fromhex('fd7bbaa9'),(hex(original_offset),prologue.hex())
candidate=bytearray(data);candidate[offset:offset+4]=prologue
assert sum(a!=b for a,b in zip(data,candidate))<=4 and len(candidate)==len(data)
target=out/'init-powerctl-restored';target.write_bytes(candidate)
record={'target':'/system/bin/init','source_sha256':hashlib.sha256(data).hexdigest(),'candidate_sha256':hashlib.sha256(candidate).hexdigest(),'offset':hex(offset),'before':data[offset:offset+4].hex(),'after':prologue.hex(),'matching_original_function_offset':hex(original_offset),'original_compiled_sha256':hashlib.sha256(raw).hexdigest(),'signature_bytes':len(signature),'unique_signature_matches':len(matches),'all_other_imported_patches_preserved':True,'installed':False,'warning':'Imported patch catalog gives fd7bbda9, which would allocate only 48 bytes and corrupt the 96-byte frame; use actual matched original fd7bbaa9.'}
(out/'powerctl-candidate.json').write_text(json.dumps(record,indent=2)+'\n')
llvm=r/'prebuilts/clang/host/linux-x86/clang-r584948b/bin/llvm-objdump'
p=subprocess.run([str(llvm),'-d','--start-address='+hex(original_offset),'--stop-address='+hex(original_offset+0x34),str(original)],capture_output=True)
(out/'matching-original-powerctl.asm.txt').write_bytes(p.stdout)
print(json.dumps(record,indent=2));print(p.stdout.decode())
