"""Exact, reviewable B16 cleanup; inventories are retained outside deletion roots."""
import argparse
from collections import Counter
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json

OWNER=BattleArtifacts('sample_battle_16')
OUT=ROOT/'docs/b16-semantic-state'
ROOTS=[OWNER.cache_dir,OWNER.report_dir]
EXTRA=[ROOT/'.cache/recognition-cleanup-b16.log']

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def inventory():
 files=[];dirs=[]
 for base in ROOTS:
  if not base.exists():continue
  if base.is_symlink():raise ValueError(base)
  for p in sorted(base.rglob('*')):
   if p.is_symlink():raise ValueError(f'Unexpected alias: {p}')
   if 'inputs' in p.relative_to(base).parts:raise ValueError(f'Preserve user inputs: {p}')
   if p.is_dir():dirs.append(str(p.relative_to(ROOT)));continue
   files.append(dict(path=str(p.relative_to(ROOT)),size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns))
 for p in EXTRA:
  if p.exists():files.append(dict(path=str(p.relative_to(ROOT)),size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns))
 tracked=set(subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines())
 if tracked & {f['path'] for f in files}:raise ValueError('Tracked files require separate review')
 video=OWNER.video()
 return dict(battle_id=OWNER.battle_id,status='dry_run',reason='User-requested cold B16 benchmark; invalidate all old B16 generated stages',
   original_video=dict(path=str(video.relative_to(ROOT)),size=video.stat().st_size,sha256=sha(video)),
   files=files,dirs=dirs,file_count=len(files),logical_bytes=sum(f['size'] for f in files),
   scope_counts={str(b.relative_to(ROOT)):sum(f['path'].startswith(str(b.relative_to(ROOT))+'/') for f in files) for b in ROOTS},
   preserved='original video; shared knowledge/models; repository source/tests/scripts; unrelated battles; concise baseline')

def main():
 p=argparse.ArgumentParser();p.add_argument('--delete-inventory',type=Path);a=p.parse_args();OUT.mkdir(exist_ok=True,parents=True)
 if not a.delete_inventory:
  data=inventory();atomic_json(OUT/'cleanup-inventory.json',data)
  print(json.dumps({k:v for k,v in data.items() if k not in {'files','dirs'}},indent=2));return
 saved=json.loads(a.delete_inventory.read_text());now=inventory()
 if saved!=now:raise ValueError('Inventory changed; regenerate and review dry run')
 # All entries are verified before any deletion. No glob-based deletion.
 for f in saved['files']:(ROOT/f['path']).unlink()
 for d in sorted(saved['dirs'],key=lambda d:len(Path(d).parts),reverse=True):(ROOT/d).rmdir()
 for b in ROOTS:
  if b.exists():b.rmdir()
 if sha(ROOT/saved['original_video']['path'])!=saved['original_video']['sha256']:raise ValueError('Video changed')
 atomic_json(OUT/'cleanup-result.json',dict(status='complete',deleted_files=saved['file_count'],deleted_logical_bytes=saved['logical_bytes'],
   inventory_sha256=sha(a.delete_inventory),original_video_unchanged=True))
 print('Deleted verified generated files:',saved['file_count'],'bytes:',saved['logical_bytes'])
if __name__=='__main__':main()
