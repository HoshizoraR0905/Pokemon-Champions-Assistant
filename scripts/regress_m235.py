"""Bounded historical event-prefix replay, isolated from original M2.3.4 outputs."""
import json
from collections import Counter
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json,fingerprint
from scripts.process_m235 import sha
import scripts.validate_m234 as validation
P=ROOT/'.cache/battles/sample_battle_5/m235'
REVISION=fingerprint({p:sha(ROOT/p) for p in validation.CODE})[:16]


class RegressionArtifacts(BattleArtifacts):
    def cache(self,name):
        if str(name).startswith('m234/'):
            return super().cache('m235/history-regression/'+REVISION+'/'+str(name)[len('m234/'):])
        return super().cache(name)


def run():
    validation.BattleArtifacts=RegressionArtifacts
    summary=P/('historical-regressions-'+REVISION+'-'+sha(__file__)[:12]+'.json')
    if summary.exists():
        saved=json.loads(summary.read_text())
        if saved['status']=='complete':
            for row in saved['results']:
                assert sha(ROOT/row['output'])==row['output_sha256']
                assert sha(BattleArtifacts(row['battle_id']).cache('m234/replay-augmented.json'))==row['original_sha256']
            preserved=json.loads((P/'prechange.json').read_text())['preserve']
            assert all(sha(ROOT/k)==v for k,v in preserved.items())
            print('Reused complete historical regression summary');return saved
    results=[]
    for i in range(5):
        bid=f'sample_battle_{i}';old_path=BattleArtifacts(bid).cache('m234/replay-augmented.json');old_hash=sha(old_path);old=json.loads(old_path.read_text())
        new=json.loads(json.dumps(validation.replay(bid,'augmented')))
        compared={k:new[k]==old[k] for k in ['excluded_frame_hashes','events','status_counts','scores','history']}
        additions=Counter()
        def established_equal(a,b):
            if type(a)!=type(b):return False
            if isinstance(a,dict):
                extra=b.keys()-a.keys()
                if extra-{'types','fainted','instance_identity_status','target','target_binding','admissibility'}:return False
                additions.update(extra)
                return a.keys()<=b.keys() and all(established_equal(v,b[k]) for k,v in a.items())
            if isinstance(a,list):return len(a)==len(b) and all(established_equal(x,y) for x,y in zip(a,b))
            return a==b
        compared['established_prefix_fields']=established_equal(old['prefixes'],new['prefixes'])
        assert sha(old_path)==old_hash,'Original historical replay overwritten'
        output=RegressionArtifacts(bid).cache('m234/replay-augmented.json')
        results.append(dict(battle_id=bid,events=new['events'],comparison=compared,projection_additions=dict(additions),status_counts=new['status_counts'],scores=new['scores'],original_sha256=old_hash,output=str(output.relative_to(ROOT)),output_sha256=sha(output)))
        atomic_json(summary,dict(status='partial',completed=len(results),new_ocr_predictions=0,results=results))
        print(bid,'semantic comparisons',compared,flush=True)
    preserved=json.loads((P/'prechange.json').read_text())['preserve'];assert all(sha(ROOT/k)==v for k,v in preserved.items())
    result=dict(status='complete',new_ocr_predictions=0,preserved_files=len(preserved),results=results,all_comparisons_equal=all(all(r['comparison'].values()) for r in results))
    atomic_json(summary,result);return result

if __name__=='__main__':run()
