"""Read the staging area; report sizes and missing targets without changing it."""
from collections import Counter
import json
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]


def git(*args, input=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, input=input)


def review():
    entries=[]
    for row in git('ls-files', '-s', '-z').decode().split('\0'):
        if not row:continue
        info,path=row.split('\t',1);mode,oid,stage=info.split()
        if stage!='0':raise ValueError('Unmerged index entry: '+path)
        entries.append({'path':path,'mode':mode,'oid':oid})
    raw=git('cat-file','--batch-check=%(objectname) %(objectsize)',input=('\n'.join(e['oid'] for e in entries)+'\n').encode()).decode().splitlines()
    for e,line in zip(entries,raw):e['git_bytes']=int(line.split()[1])
    headids={line.split()[2] for line in git('ls-tree','-r','HEAD').decode().splitlines()}
    added={e['oid']:e['git_bytes'] for e in entries if e['oid'] not in headids}
    changes=[row for row in git('diff','--cached','--name-status','--no-renames','-z').decode().split('\0') if row]
    pairs=list(zip(changes[::2],changes[1::2]));tracked={e['path'] for e in entries};broken=[]
    for e in entries:
        if e['mode']!='120000':continue
        p=ROOT/e['path'];target=p.resolve()
        if not p.exists():broken.append(e['path'])
        elif not target.is_relative_to(ROOT) or target.relative_to(ROOT).as_posix() not in tracked:
            broken.append(e['path']+' -> untracked or external target')
    ignored=[p for p in git('ls-files','-ci','--exclude-standard','-z').decode().split('\0') if p]
    return {'tracked_files':len(entries),'tracked_blob_bytes':sum(e['git_bytes'] for e in entries),
            'unique_new_blob_bytes_vs_HEAD':sum(added.values()),'changed_paths':len(pairs),
            'changes_by_status':dict(Counter(s for s,p in pairs)),
            'largest_tracked_files':sorted(entries,key=lambda e:e['git_bytes'],reverse=True)[:15],
            'proposed_tracking':[e['path'] for e in entries],
            'staged_changes':[{'status':s,'path':p} for s,p in pairs],
            'broken_or_untracked_symlink_targets':broken,'ignored_paths_still_in_index':ignored}


if __name__=='__main__':
    result=review();destination=ROOT/'reports/git-tracking-review.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('proposed_tracking','staged_changes','largest_tracked_files')},indent=2))
    print('Complete file lists and largest tracked files: '+str(destination))
