"""Bounded cache-first UI evidence stages. Historical caches are read-only."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib,json,re,sys,time,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json,fingerprint
P=BattleArtifacts('sample_battle_5',ROOT).cache('m236u')
OLD=BattleArtifacts('sample_battle_5',ROOT).cache('m236')
FIXTURE=ROOT/'tests/fixtures/battles/m236u_ui_review.json'
CODE=['recognition/ui_regions.py','recognition/message_occurrences.py','battle_events/parser.py','tracking/state_engine.py',
      'scripts/process_m236u.py','recognition/visual_evidence.py','recognition/message_selection.py','recognition/identity_events.py']


def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()


class ScopedArtifacts(BattleArtifacts):
    def cache(self,name):
        if str(name).startswith('m235/reads/'):
            leaf=Path(name).name
            for scope in ['m235','m236']:
                old=super().cache(scope+'/reads/'+leaf)
                if old.exists():return old
            return super().cache('m236u/reads/'+leaf)
        if name=='m235/reads':return super().cache('m236u/reads')
        return super().cache(name)


def ocr_cache():
    from scripts.process_m235 import CropCache
    cache=CropCache(ScopedArtifacts('sample_battle_5',ROOT),96,cache_only=False)
    backend=cache.load();predict=backend.predict;ledger=P/'ocr-ledger.json'
    if not ledger.exists():atomic_json(ledger,dict(total=0,limit=96,reservations=[]))
    def bounded(crops):
        result=[]
        for crop in crops:
            key=fingerprint(dict(shape=list(crop.shape),pixels=hashlib.sha256(crop.tobytes()).hexdigest(),**cache.identity))
            path=cache.paths.cache('m235/reads/'+key+'.json')
            if not path.exists():
                d=json.loads(ledger.read_text())
                if d['total']>=d['limit']:raise RuntimeError('Independent M236-U OCR budget exhausted')
                d['total']+=1;d['reservations'].append(dict(key=key,status='reserved'));atomic_json(ledger,d)
                try:value=predict([crop])[0]
                except Exception as exc:
                    d['reservations'][-1].update(status='error',error=repr(exc));atomic_json(ledger,d);raise
                d['reservations'][-1]['status']='complete';atomic_json(ledger,d);result.append(value)
            else:result+=predict([crop])
        return result
    backend.predict=bounded;return cache


def source_rows(split):
    fixture=json.loads(FIXTURE.read_text())
    if split=='held_out':return [{k:v for k,v in r.items() if k not in {'expected','split'}} for r in fixture['cases'] if r['split']==split]
    # Previously exposed examples are diagnostic regressions, never new held-out.
    selected=[]
    for part in ['development','held_out']:
        d=json.loads((OLD/f'{part}-observations.json').read_text())
        for r in d['observations']:
            if any(abs(r['timestamp']-t)<.035 for t in [287.015,408.002,413.503,415.503,416.003,416.503,417.003,417.503,424.005,425.505,426.005,426.503,427.005,430.005]):
                selected.append(deepcopy(r))
    selected += [{k:v for k,v in r.items() if k not in {'expected','split'}} for r in fixture['cases'] if r['split']=='development']
    old=json.loads(BattleArtifacts('sample_battle_5',ROOT).cache('m235/final-observations.json').read_text())
    selected += [deepcopy(r) for r in old['observations'] if abs(r['timestamp']-128.021667)<.035]
    return sorted(selected,key=lambda r:r['timestamp'])


def freeze():
    seal=dict(code={f:sha(ROOT/f) for f in CODE},fixture_sha256=sha(FIXTURE),status='frozen_before_u_held_out')
    target=P/'implementation-seal.json'
    if target.exists():assert json.loads(target.read_text())==seal,'Do not reseal exposed held-out evaluation'
    else:atomic_json(target,seal)


def recognize(split):
    import cv2
    from recognition.ui_regions import inspect_ui,read_message
    seal=json.loads((P/'review-seal.json').read_text());assert sha(FIXTURE)==seal['sha256']
    code={f:sha(ROOT/f) for f in CODE};recipe=fingerprint(code)
    if split=='held_out':assert json.loads((P/'implementation-seal.json').read_text())['code']==code
    rows=source_rows(split);cache=ocr_cache();output=[];started=time.monotonic()
    for i,row in enumerate(rows):
        target=P/'observations'/f'{recipe}-{row["sha256"]}.json'
        if target.exists():result=json.loads(target.read_text())
        else:
            assert sha(ROOT/row['image'])==row['sha256']
            image=cv2.imread(str(ROOT/row['image']));ui=inspect_ui(image)
            region=next((r for r in ui['regions'] if r['region_type']=='battle_message'),None)
            message=read_message(image,cache,region) if region else dict(selected=False,raw_text='',confidence=0.,reason='overlay_specific_layout',rows=[])
            for r in ui['regions']:
                if r['region_type']=='battle_message':
                    r['selected_for_ocr']=message['selected'];r['ocr']=message
                if r['region_type']=='field_indicator' and r['visibility']=='partial':
                    # Literal header evidence only; no inferred remaining duration.
                    from recognition import box
                    reads={key:asdict(cache.read(image,box(image,roi))) for key,roi in
                           [('label',(.205,.045,.30,.095)),('counter',(.39,.045,.424,.095))]}
                    r['selected_for_ocr']=True;r['ocr']=reads
                    label=reads['label']['raw_text'].strip();counter=reads['counter']['raw_text'].strip()
                    if label in {'沙暴状态','晴天','雨天','下雪','精神场地','青草场地','戏法空间'} and reads['label']['confidence']>=.9:
                        r['visibility']='visible';r['canonical']=dict(literal_label=label,literal_counter=counter,
                            observed_at=row['timestamp'],counter_meaning='unverified',trigger_time=None)
            # Reuse the established party/banner extraction receipts, without
            # asserting active occupancy or uncalibrated banner side.
            for r in ui['regions']:
                if r['region_type']=='party_overlay' and row.get('party_panel'):
                    r['fields']['cached_extraction']=deepcopy(row['party_panel']['parsed'])
                    r['fields']['active_slot']=None
                if r['region_type']=='ability_banner':
                    values=[v for v in row.get('visual',{}).get('parsed',[]) if v.get('kind')=='popup']
                    r['fields']['cached_extraction']=deepcopy(values)
                    r['admission']=dict(status='unresolved',reason='Screen edge alone does not identify an activating side or instance')
                if r['region_type']=='active_hud' and r['visibility']=='visible':
                    mon=next((m for m in row.get('snapshot',{}).get('pokemon',[]) if m['slot']==r['region_id']),None)
                    if mon:
                        r['ocr']=dict(species=deepcopy(mon['species']),hp=deepcopy(mon['hp']),icon=deepcopy(mon['icon']))
                        r['canonical']=deepcopy(mon['species'].get('resolution'))
                        r['fields']['recognition_source']='compatible_frozen_m236_prediction_reused'
            result=dict(**{k:v for k,v in row.items() if k not in {'snapshot','visual','party_panel','message'}},
                ui=ui,message=message,baseline_message=deepcopy(row.get('message')),
                cached_snapshot=deepcopy(row.get('snapshot',{})))
            atomic_json(target,result)
        output.append(result)
        atomic_json(P/f'{split}-progress.json',dict(status='partial',complete=i+1,total=len(rows),recipe=recipe))
        print(split,i+1,'/',len(rows),'new OCR ledger',json.loads((P/'ocr-ledger.json').read_text())['total'],flush=True)
    # Group only contiguous observations; sparse diagnostic frames never bridge
    # missing video coverage. No review fixture is passed into this adapter.
    from recognition.message_occurrences import MessageOccurrences
    groups=MessageOccurrences('sample_battle_5');decisions=[];events=[]
    for row in sorted(output,key=lambda r:r['timestamp']):
        d=groups.observe(row);events+=d['events'];decisions.append(dict(timestamp=row['timestamp'],**d))
    result=dict(status='complete',recipe=recipe,split=split,frames=output,occurrences=groups.groups,
                prefix_decisions=decisions,events=events,seconds=time.monotonic()-started,ocr_cache_hits=cache.hits)
    atomic_json(P/f'{split}-results.json',result)
    atomic_json(P/f'{split}-progress.json',dict(status='complete',complete=len(rows),total=len(rows),recipe=recipe))
    return result


def evaluate():
    fixture=json.loads(FIXTURE.read_text());rows=json.loads((P/'held_out-results.json').read_text())['frames'];by={r['sha256']:r for r in rows}
    scored=[]
    from battle_events.parser import EventParser
    for label in fixture['cases']:
        if label['split']!='held_out':continue
        row=by[label['sha256']];expected=label['expected'];regions=row['ui']['regions']
        message=row['message'];parsed=EventParser().parse(dict(entry_id=row['sha256'],source_id=row['source_id'],raw_text=message['raw_text'],ocr_confidence=message['confidence'],source_region_type='battle_message'))
        normalized=lambda t:''.join(unicodedata.normalize('NFKC',t or '').split())
        scored.append(dict(timestamp=row['timestamp'],sha256=row['sha256'],expected=expected,
            message_visible=any(r['region_type']=='battle_message' and r['visibility']=='visible' for r in regions),
            message_selected=message['selected'],text_correct=normalized(message['raw_text'])==normalized(expected.get('message')),
            rows_read=len(message['rows']),canonical_event=parsed.event_type,
            canonical_move=(parsed.canonical_references.get('move') or {}).get('canonical_id'),
            overlay=row['ui']['overlay'],visible_hud=sum(r['region_type']=='active_hud' and r['visibility']=='visible' for r in regions),
            partial_hud=sum(r['region_type']=='active_hud' and r['visibility']=='partial' for r in regions)))
    positives=[r for r in scored if r['expected'].get('message')]
    negatives=[r for r in scored if not r['expected'].get('message')]
    metrics=dict(reviewed_frames=len(scored),actual_reviewed_message_occurrences=len(positives),
        positive_messages_selected=sum(r['message_selected'] for r in positives),correct_transcriptions=sum(r['text_correct'] for r in positives),
        negative_message_regions=len(negatives),false_positive_message_schedules=sum(r['message_selected'] for r in negatives),
        false_positive_semantic_candidates=sum(r['canonical_event']!='unknown' for r in negatives),
        message_occurrence_types_identified=sum(r['canonical_event']!='unknown' for r in positives),
        reviewed_executed_move_occurrences=sum(r['expected'].get('kind')=='move_execution' for r in scored),
        isolated_hud_layout_cases=sum(r['expected']['hud']==1 for r in scored),
        isolated_hud_detected=sum(r['visible_hud']+r['partial_hud']>0 for r in scored if r['expected']['hud']==1))
    out=dict(status='complete',metrics=metrics,cases=scored,independence='New UI labels, pre-tuning freeze; same recording and prior phase-survey exposure. Three sparse message occurrences are not whole-battle coverage.')
    atomic_json(P/'evaluation.json',out);print(json.dumps(metrics),flush=True)


def replay_regressions():
    """Existing event/state architecture; replace only new inspected messages.

    All unmodified observations remain explicitly the frozen baseline. This is a
    diagnostic integration replay, not an independent full-window UI evaluation.
    """
    from recognition.identity_events import events_from_observations
    from tracking.state_engine import StateEngine,EventRecord,event_from_dict,ordering
    from tracking.battle_state import BattleState
    data=json.loads((P/'development-results.json').read_text())
    changes={r['sha256']:r for r in data['frames']}
    emitted={e['evidence'][0]['observation_ids'][0] for e in data['events']}
    baseline=json.loads((OLD/'development-observations.json').read_text())
    baseline['observations']+=json.loads((OLD/'held_out-observations.json').read_text())['observations']
    for r in baseline['observations']:
        change=changes.get(r['sha256'])
        if change:
            r['message']=deepcopy(change['message']) if r['sha256'] in emitted else dict(raw_text='',confidence=0.)
            if change['ui']['overlay']:r['snapshot']['pokemon']=[]
    events=events_from_observations(baseline,'sample_battle_5')
    engine=StateEngine(BattleState('sample_battle_5',knowledge=dict(reliability_v1=True,reliability_v2=True,identity_v1=True)))
    for i,e in enumerate(events,1):
        e['attributes']['sequence']=i
        if e['event_type'] not in {'hud_observation','coverage_observation','preview_observation'}:
            e['attributes']['source_region_type']='battle_message'
        engine.history.append(EventRecord(e,i,ordering(event_from_dict(e))))
    prefixes={}
    def capture(record,state):
        t=record.event['attributes']['observation_time']
        if 413<=t<=428:
            prefixes[str(t)]=[dict(instance_id=pid,moves=[v['move']['canonical_id'] for v in p.moves.executed])
                              for pid,p in state.pokemon.items() if p.moves.executed]
    engine.replay(snapshot_callback=capture)
    result=dict(status='complete',evaluation_kind='diagnostic baseline plus inspected U messages; not pristine evaluation',
        engine=engine.to_dict(),prefix_revealed_moves=prefixes,
        executed_event_receipts=[dict(timestamp=r.event['attributes']['observation_time'],event=r.event,
            status=r.application_status,reason=r.reason,bindings=r.bindings) for r in engine.history if r.event['event_type']=='move_execution'])
    atomic_json(P/'regression-replay.json',result)
    print('Diagnostic existing-state replay complete; execution receipts',len(result['executed_event_receipts']),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['development','freeze','held_out','evaluate','replay'],required=True);args=parser.parse_args()
    P.mkdir(parents=True,exist_ok=True);manifest=P/'stages'/f'{args.stage}.json'
    atomic_json(manifest,dict(status='running',runner=sha(__file__)))
    try:
        if args.stage=='freeze':freeze()
        elif args.stage=='evaluate':evaluate()
        elif args.stage=='replay':replay_regressions()
        else:recognize(args.stage)
        atomic_json(manifest,dict(status='complete',runner=sha(__file__)))
    except Exception as exc:
        atomic_json(manifest,dict(status='error',error=repr(exc),resume=f'.venv/bin/python scripts/process_m236u.py --stage {args.stage}'));raise


if __name__=='__main__':main()
