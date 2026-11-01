"""Read-only hashes of focused inputs, preserved prior traces and frozen seals."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNS={20:'fresh-b20-postfix-v1',21:'fresh-b21-context-v1',22:'fresh-b22-ditto-20261030-v1',23:'mega-b23-20261030-v1'}
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_text())
def main():
    checked={};issues=[];battles={}
    def check(p,expected):
        key=str(p.relative_to(ROOT))
        if key in checked:
            if checked[key]!=expected:issues.append(dict(path=key,reason='conflicting recorded hash'))
            return
        checked[key]=expected
        if not p.exists() or sha(p)!=expected:issues.append(dict(path=key,reason='missing or hash mismatch'))
    old_count=0
    for n,run in RUNS.items():
        base=ROOT/f'.cache/battles/sample_battle_{n}'
        seal=base/f'event-driven/{run}/video-only-seal.json'
        for p,h in read(seal)['files'].items():check(seal.parent/p,h)
        for namespace in ['hidden-constraints-20261031-v1','hidden-integration-20261101-v1','focused-repair-20261101-v1']:
            folder=base/'diagnosis'/namespace;m=read(folder/'manifest.json')
            for p,h in m['identity']['inputs'].items():check(ROOT/p,h)
            for key,stage in m['stages'].items():
                if stage.get('status')!='complete':continue
                if key.startswith('trace:'):
                    for p,h in stage['outputs'].items():
                        check(folder/p,h)
                        if namespace!='focused-repair-20261101-v1':old_count+=1
                    if stage.get('report'):check(ROOT/stage['report'],stage['report_sha256'])
        latest=read(base/'diagnosis/focused-repair-20261101-v1/latest.json');t=read(ROOT/latest['trace'])
        assert not t['context_validation']['receipt_status_mismatches'], (n,'new status mismatch')
        battles[n]=dict(trace=latest['trace'],aliases=t['focused_repair']['aliases'],repairs=len(t['focused_repair']['hp_repairs']),source_conflicts=len(t['source_state_conflicts']),inference_contradictions=len(t['contradictions']))
    result=dict(checked_unique_files=len(checked),preserved_prior_trace_json_outputs=old_count,issues=issues,battles=battles,
        scope='Source identities/seals and declared completed stage outputs; not a repeat of every historical artifact guard or recognition accuracy evaluation')
    dest=ROOT/'docs/focused-repair-20261101/integrity.json';dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(checked=len(checked),preserved_prior_outputs=old_count,issues=len(issues))))
    if issues:raise SystemExit(1)
if __name__=='__main__':main()
