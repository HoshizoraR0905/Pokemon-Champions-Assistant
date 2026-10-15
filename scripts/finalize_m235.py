"""Recover M2.3.5 with immutable revision outputs and zero OCR inference."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.process_m235 import sha,replay,ScopedArtifacts
from recognition.video_sampling import atomic_json,fingerprint
P=ROOT/'.cache/battles/sample_battle_5/m235'
CODE=['recognition/icons.py','recognition/message_selection.py','recognition/message_recovery.py','recognition/party_panel.py','recognition/hud_reuse.py','recognition/repeat_evidence.py','recognition/visual_adapter.py','tracking/reliability.py','tracking/evidence_projection.py','tracking/evidence_fusion.py','tracking/state_engine.py','scripts/process_m235.py','scripts/finalize_m235.py']


def identity():
    pre=json.loads((P/'prechange.json').read_text())
    return dict(code={p:sha(ROOT/p) for p in sorted(set(CODE)|set(pre['code']))},input_sha256=sha(P/'final-observations.json'),review_seal_sha256=sha(P/'review-seal.json'))


def revision_dir():return P/'revisions'/fingerprint(identity())


def prepare():
    import cv2
    from recognition.icons import IconRecognizer
    from recognition.entities import EntityResolver
    from recognition.identity import combine_identity
    from recognition.repeat_evidence import RepeatEvidence
    from models import Observation,RawOCR
    code=identity();target=revision_dir();target.mkdir(parents=True,exist_ok=True)
    manifest=target/'manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old['status']=='complete' and old['identity']==code and sha(target/'observations.json')==old['output_sha256']:
            print('Reused complete recovery revision');return target
    rows=json.loads((P/'final-observations.json').read_text())['observations'];output=[];icons=IconRecognizer(color_sensitive=True);resolver=EntityResolver();repeats=RepeatEvidence()
    atomic_json(manifest,dict(status='running',identity=code))
    for row in rows:
        image=cv2.imread(str(ROOT/row['image']));per=target/'frames'/(row['sha256']+'.json');repeat=repeats.observe(row,image)
        if per.exists():out=json.loads(per.read_text())
        else:
            out=deepcopy(row);out['repeat_evidence']=repeat
            for mon in out.get('snapshot',{}).get('pokemon',[]):
                old=mon['species'];raw=old.get('raw_ocr');text=Observation(confidence=old['confidence'],region=old['region'],raw_text=old['raw_text'],raw_ocr=RawOCR(**raw) if raw else None)
                text=resolver.resolve(text,'species',region_kind='species')
                icon=icons.identify(image,mon['icon']['region'])
                mon['icon']=asdict(icon);mon['species']=asdict(combine_identity(text,icon,resolver.knowledge))
            atomic_json(per,out)
        output.append(out)
        atomic_json(target/'progress.json',dict(status='partial',completed=len(output),total=len(rows),new_ocr_predictions=0))
        if row.get('snapshot'):print('Reused OCR; refreshed icon candidates',row['timestamp'],flush=True)
    atomic_json(target/'observations.json',dict(status='complete',battle_id='sample_battle_5',observations=output,additional_cached_observations=[]))
    atomic_json(manifest,dict(status='complete',identity=code,output_sha256=sha(target/'observations.json'),new_ocr_predictions=0,frames=len(output)))
    return target


def replay_revision():
    target=revision_dir();manifest=json.loads((target/'manifest.json').read_text());assert manifest['identity']==identity()
    assert sha(target/'observations.json')==manifest['output_sha256']
    seal=target/'replay-seal.json'
    if seal.exists():
        assert sha(target/'replay.json')==json.loads(seal.read_text())['sha256'];print('Reused recovery replay');return target
    replay(ScopedArtifacts('sample_battle_5'),'final',observations_name=str((target/'observations.json').relative_to(P)),output_name=str((target/'replay.json').relative_to(P)))
    atomic_json(seal,dict(identity=identity(),sha256=sha(target/'replay.json')));return target


def freeze():
    target=revision_dir();assert (target/'replay-seal.json').exists()
    seal=dict(status='frozen_before_held_out_scoring',identity=identity(),outputs={str((target/name).relative_to(ROOT)):sha(target/name) for name in ['observations.json','replay.json','manifest.json','replay-seal.json']},evaluation_code_sha256=sha(ROOT/'scripts/score_m235.py'),ocr_predictions=0)
    path=P/'implementation-seal.json'
    if path.exists():assert json.loads(path.read_text())==seal,'Frozen implementation changed'
    else:atomic_json(path,seal)
    print('Frozen implementation',target.name);return target

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['prepare','replay','freeze'],required=True);a=p.parse_args()
    {'prepare':prepare,'replay':replay_revision,'freeze':freeze}[a.stage]()
