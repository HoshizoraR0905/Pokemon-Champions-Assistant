"""Read-only scoped B16 before/after summary; never decodes video or runs OCR."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts,canonical_id
from recognition.video_sampling import atomic_json
from recognition.event_report import verify_seal
from recognition.fast_video import digest


def read(path):return json.loads(path.read_text())


def summary(owner,run):
    cache=owner.cache('evaluation/'+run+'/state-benchmark')
    comparisons=read(cache/'event-comparisons.json')
    facts={f['fact_id']:f for f in read(cache/'reference-facts.json')['facts']}
    numeric=[x for x in comparisons if x['category'] in {'damage','healing'}]
    pairs={}
    for side,unit in [('self','absolute'),('opponent','displayed_percent')]:
        rows=[x for x in numeric if facts[x['fact_id']]['side']==side and facts[x['fact_id']]['unit']==unit]
        pairs[side]=dict(correct=sum(x['status']=='correct_applied' for x in rows),evaluable=len(rows),unit=unit)
    live=owner.cache('event-driven/'+run);verify_seal(live)
    replay=read(live/'replay.json')
    links=[o for p in replay['state']['pokemon'].values() for o in p['hp']['observations']
        if o.get('delta') and o.get('cause')]
    return dict(metrics=read(cache/'metrics.json'),numeric_pairs=pairs,
        numeric_endpoint_pairs=dict(correct=sum(x['status']=='correct_applied' for x in numeric),evaluable=len(numeric)),
        proposed_numeric_cause_links=len(links),independently_verified_numeric_cause_links=None,
        numeric_cause_note='Reference has explicit burn notices but no independently verified numeric cause/amount pairs; numeric causal accuracy is unmeasured.',
        deferred=Counter(h['reason'] for h in replay['history'] if h['application_status']=='deferred'),
        seals=dict(prediction=digest(live/'video-only-seal.json'),reference=digest(cache/'reference-seal.json')))


def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--baseline',default='b16-semantic-state-20261027-v1');a=p.parse_args()
    owner=BattleArtifacts('sample_battle_16');run=canonical_id(a.run_id);baseline=canonical_id(a.baseline)
    if run==baseline:p.error('Updated run must differ from baseline')
    result=dict(battle_id=owner.battle_id,baseline_run=baseline,updated_run=run,evaluation='B16 development/regression; cached source pixels; not held out',
        before=summary(owner,baseline),after=summary(owner,run),
        sampling_limit='1276 saved inspected frames; 232 COMMAND monitoring-only cells lack pixels; no fresh full-grid acquisition or performance claim.')
    if result['before']['seals']['reference']!=result['after']['seals']['reference']:
        raise ValueError('Before/after must use the identical sealed reference')
    old=owner.cache('evaluation/'+baseline+'/state-benchmark');new=owner.cache('evaluation/'+run+'/state-benchmark')
    previous={x['fact_id']:x for x in read(old/'event-comparisons.json')}
    points=read(old/'live-checkpoint-projections.json')['hp']
    facts={f['fact_id']:f for f in read(new/'reference-facts.json')['facts']}
    gains=[]
    for row in read(new/'event-comparisons.json'):
        if (row['category'] not in {'damage','healing'} or row['status']!='correct_applied'
                or previous[row['fact_id']]['status']=='correct_applied'):continue
        fact=facts[row['fact_id']];pair=row['hp_endpoint_pair'];lo=row['source_window']['start'];hi=row['source_window']['end']
        compatible=[p for p in points if p['pid']==pair[1]['pid'] and p['unit']==fact['unit']]
        present=any(a['value']==fact['before'] and b['value']==fact['after'] and a['time']<b['time']
            and lo-1<=b['time']<=hi+1 for a in compatible for b in compatible)
        gains.append(dict(fact_id=row['fact_id'],unit=fact['unit'],side=fact['side'],
            before=fact['before'],after=fact['after'],updated_window=dict(start=lo,end=hi),
            baseline_pair_already_present_under_updated_anchors=present,
            classification='alignment_window_only; no new capture credit' if present else 'new accepted endpoint evidence required',
            endpoint_evidence=pair))
    result['numeric_pair_gain_audit']=gains
    destination=owner.report('evaluation/'+run+'/before-after.json');atomic_json(destination,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
