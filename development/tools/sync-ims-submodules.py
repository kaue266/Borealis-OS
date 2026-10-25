#!/usr/bin/env python3
"""Restore the two public IMS audio dependencies at their recorded gitlink pins."""
from pathlib import Path
import json
import subprocess

root=Path('/home/android/borealisos-android17/packages/apps/PhhIms')
package=Path(__file__).resolve().parent.parent
expected={
 'app/jni/rnnoise':('https://github.com/amikhasenko/rnnoise','f94e734aa504e34100516c7d486cf69fc4174f00'),
 'app/jni/webrtc-aec3':('https://github.com/ewan-xu/AEC3.git','6b11f0f31cd10f6bf68025ccad771f545d87dbce'),
}
proof=[]
for path,(url,commit) in expected.items():
 gitlink=subprocess.check_output(['git','ls-tree','HEAD','--',path],cwd=root,text=True).split()
 assert gitlink[:3]==['160000','commit',commit],(path,gitlink)
 actual_url=subprocess.check_output(['git','config','-f','.gitmodules','--get','submodule.'+path+'.url'],cwd=root,text=True).strip()
 assert actual_url==url,(path,actual_url)
 subprocess.run(['git','submodule','update','--init','--',path],cwd=root,check=True)
 actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root/path,text=True).strip()
 assert actual==commit,(path,actual)
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=root/path,text=True).strip()
 proof.append({'path':path,'url':url,'commit':actual})
(package/'validation/ims-submodules.json').write_text(json.dumps(proof,indent=2)+'\n')
print('IMS audio submodules restored and pinned; no source scripts executed.')
