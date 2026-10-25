#!/usr/bin/env python3
"""Apply source deltas to pinned bases; no device access or build."""
import argparse,json,subprocess,shutil
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--root',required=True,type=Path)
choice=parser.add_mutually_exclusive_group(required=True)
choice.add_argument('--check',action='store_true');choice.add_argument('--apply',action='store_true')
args=parser.parse_args();root=args.root.resolve();package=Path(__file__).resolve().parents[1]
if root==Path('/') or not (root/'.repo').is_dir():raise SystemExit('Expected an existing Repo source checkout.')
index=json.loads((package/'patches/index.json').read_text());pending=[]
for item in index:
 directory=root/item['path'];patch=package/item['patch']
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=directory,text=True).strip()
 if head!=item['base_commit']:raise SystemExit('Base commit mismatch: '+item['path'])
 check=subprocess.run(['git','apply','--check',str(patch)],cwd=directory,capture_output=True)
 if check.returncode:
  reverse=subprocess.run(['git','apply','--reverse','--check',str(patch)],cwd=directory,capture_output=True)
  if reverse.returncode:raise SystemExit('Patch conflicts with tree: '+item['path'])
 else:pending.append((directory,patch))
overlay=[]
for src in sorted((package/'overlay').rglob('*')):
 if not src.is_file():continue
 rel=src.relative_to(package/'overlay');dest=root/rel
 if not dest.resolve().is_relative_to(root):raise SystemExit('Path escapes checkout: '+str(rel))
 overlay.append((src,dest))
print('Validated %d patch bases; %d source overlay files.'%(len(index),len(overlay)))
if args.apply:
 for directory,patch in pending:subprocess.run(['git','apply',str(patch)],cwd=directory,check=True)
 for src,dest in overlay:
  dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
 print('Sources applied. This does not build or validate an installable ROM.')
