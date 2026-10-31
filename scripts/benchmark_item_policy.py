"""Summarize sealed Practical/Comprehensive packages, never decode or run OCR."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_evidence.speed_replay_offline import file_hash,atomic


def summarize(number,profile):
    cache=ROOT/f'.cache/battles/sample_battle_{number}/m342-offensive'
    pointer=json.loads((cache/f'latest-{profile}.json').read_text());path=Path(pointer['path'])
    seal=json.loads(path.with_name('manifest.json').read_text())
    if seal['status']!='complete' or file_hash(path)!=seal['outputs']['replay.json']:raise ValueError('Unsealed benchmark package')
    replay=json.loads(path.read_text());updates=replay['offensive_inference']['updates'];final=updates[-1]['full']
    hits=[]
    for u in updates:
        h=u['full']['updates'][-1]
        hits.append(dict(id=u['id'],incremental_seconds=h['incremental_seconds'],forward_evaluations=h['forward_evaluations'],
            before={k:v for k,v in h['before'].items() if k in {'configuration_classes','compact_rows','items','abilities'}},
            after={k:v for k,v in h['after'].items() if k in {'configuration_classes','compact_rows','joint_allocations','items','abilities','values','speed'}},
            unresolved_classes=h['unresolved_after']['configuration_classes'],
            numerical_excluded_classes=len(h['numerical_excluded_ids']),item_evidence_excluded_classes=len(h['item_evidence_excluded_ids']),
            policy=u['item_policy'],
            attack=h['after_offensive_stats']['attack']['values']['values'],special_attack=h['after_offensive_stats']['special_attack']['values']['values'],speed=h['after']['speed']['values']))
    return dict(battle=number,profile=profile,path=str(path.relative_to(ROOT)),input_identity=seal['identity'],
        total_package_seconds=seal['metrics']['seconds'],peak_rss_bytes=seal['metrics']['peak_rss_bytes'],replay_json_bytes=path.stat().st_size,
        initial_concrete_classes=hits[0]['before']['configuration_classes'],initial_compact_rows=hits[0]['before']['compact_rows'],
        final_unresolved_items=final['requirements']['unresolved_items'],forward_evaluations=final['work']['forward_evaluations'],hits=hits)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    rows=[summarize(n,p) for n in (11,12) for p in ('practical','comprehensive')]
    for n in (11,12):
        a,b=[r for r in rows if r['battle']==n]
        for key in ('inputs',):
            # All evidence/mechanics hashes must match; only profile identity differs.
            assert a['input_identity'][key]==b['input_identity'][key]
    atomic(args.output,dict(version='m343b-item-policy-benchmark-v1',rows=rows,
        notes=['Same evidence, solver and representation; Practical omissions are modeling assumptions, not damage exclusions.',
               'Incremental time includes joint filtering/projections; excludes domain initialization and checkpoint/package writes.',
               'Package time includes evidence loading, domain initialization, projections and writes; cold build metrics retained in seal.',
               'Peak RSS includes Python runtime, evidence/knowledge and packaging. No recognition accuracy measured.']))
    for r in rows:print(r['battle'],r['profile'],r['total_package_seconds'],[h['incremental_seconds'] for h in r['hits']],r['forward_evaluations'],r['peak_rss_bytes'],r['replay_json_bytes'])
