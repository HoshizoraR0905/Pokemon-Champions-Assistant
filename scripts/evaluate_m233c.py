"""Independent C scoring. Labels are consumed here, never by recognition."""
import collections,hashlib,importlib.util,json,re,resource,subprocess,sys,time
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_events.parser import EventParser
from battle_events.schema import Evidence,stable_id
from recognition.video_sampling import atomic_json,fingerprint
from recognition.message_selection import SelectionConfig,MessageSelector
from tracking.state_engine import StateEngine,EventRecord,ordering,event_from_dict
from tracking.battle_state import BattleState,from_dict
from tracking.hidden_state import HiddenEngine
from scripts.validate_m233c import INTERVALS,preserve

FIXTURE=ROOT/'tests/fixtures/battles/m233c_semantic_review.json'

def legacy_parser():
    code=subprocess.check_output(['git','show','0a3cf19:battle_events/parser.py'],cwd=ROOT)
    p=ROOT/'.cache/m233c/frozen_parser.py';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(code)
    spec=importlib.util.spec_from_file_location('battle_events.c_baseline',p);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    return m.EventParser


def compact(text):return re.sub(r'[\s！!。.,，]','',text)


def interval_score(labels,oldparser):
    import cv2
    bid=labels['battle_id'];base=ROOT/f'.cache/battles/{bid}/m233c';m=json.loads((base/'ocr-manifest.json').read_text());data=json.loads((ROOT/m['observations']).read_text())
    scores=collections.Counter();details=[];captured=set();selected=set();text_good=set();type_good=set();move_good=set();old_type_good=set();old_move_good=set()
    # Match nominal target cell to independently labeled reference index; PTS
    # differences are explicit, ambiguous fades excluded from frame precision.
    for row in data['frames']:
        nearest=min(labels['frames'],key=lambda r:abs(r['timestamp']-row['timestamp']))
        gt=next((o for o in labels['occurrences'] if o['occurrence_id']==nearest['occurrence_id']),None)
        if gt:captured.add(gt['occurrence_id'])
        is_selected=row['selection']['selected']
        if is_selected:
            if gt:selected.add(gt['occurrence_id'])
            elif nearest['label']=='no_message':scores['false_positive_selections']+=1
            else:scores['ambiguous_selected_frames']+=1
        message=row.get('message')
        if message:
            e=EventParser().parse(dict(entry_id=row['sha256'],raw_text=message['raw_text'],ocr_confidence=message['confidence']))
            old=oldparser().parse(dict(entry_id=row['sha256'],raw_text=message['raw_text'],ocr_confidence=message['confidence']))
            move=(e.canonical_references.get('move') or {}).get('canonical_id');oldmove=(old.canonical_references.get('move') or {}).get('canonical_id')
            if gt:
                oid=gt['occurrence_id']
                if compact(message['raw_text'])==compact(gt['expected_text']):text_good.add(oid)
                if e.event_type==gt['expected_type']:type_good.add(oid)
                if old.event_type==gt['expected_type']:old_type_good.add(oid)
                if gt['canonical_move'] and move==gt['canonical_move']:move_good.add(oid)
                if gt['canonical_move'] and oldmove==gt['canonical_move']:old_move_good.add(oid)
                if move and move!=gt['canonical_move']:scores['false_move_assignments']+=1
            details.append(dict(timestamp=row['timestamp'],ground_truth=gt['occurrence_id'] if gt else None,text=message['raw_text'],type=e.event_type,move=move,actor=(e.actor or {}).get('canonical_id'),side=e.side,uncertainty=e.uncertainty))
    # Controlled selector comparison: same 2 FPS frames, no OCR for other policy.
    selectors={p:MessageSelector(SelectionConfig(policy=p)) for p in ['baseline','hybrid']};policy_sets={p:set() for p in selectors}
    for row in data['frames']:
        near=min(labels['frames'],key=lambda r:abs(r['timestamp']-row['timestamp']))
        im=cv2.imread(str(ROOT/row['image']))
        for p,selector in selectors.items():
            if selector.select(im,row['phase'],timestamp=row['timestamp'])['selected'] and near['occurrence_id']:policy_sets[p].add(near['occurrence_id'])
    return dict(battle_id=bid,occurrences=len(labels['occurrences']),captured=len(captured),selected=len(selected),correct_text=len(text_good),correct_type=len(type_good),correct_move=len(move_good),move_denominator=sum(bool(o['canonical_move']) for o in labels['occurrences']),old_correct_type=len(old_type_good),old_correct_move=len(old_move_good),frame_counts=dict(collections.Counter(f['label'] for f in labels['frames'])),scores=dict(scores),policy_occurrences={p:len(v) for p,v in policy_sets.items()},performance=m,readings=details)


def event_time(e):return e['attributes'].get('observation_time',e['evidence'][0]['details'].get('timestamp',float('-inf')))


def input_events(bid):
    # Existing automatic A inputs only: no Battle Logs or corrected states.
    events=json.loads((ROOT/f'reports/battles/{bid}/M2.3.3-A-events.json').read_text())['events']
    if bid in INTERVALS:
        m=json.loads((ROOT/f'.cache/battles/{bid}/m233c/ocr-manifest.json').read_text());d=json.loads((ROOT/m['observations']).read_text())
        hashes={oid for e in events for source in e['evidence'] for oid in source['observation_ids']}
        for row in d['frames']:
            if not row.get('message') or row['sha256'] in hashes:continue
            e=EventParser().parse(dict(entry_id='C:'+row['sha256'],source_id=row['source_id'],observation_ids=[row['sha256']],raw_text=row['message']['raw_text'],ocr_confidence=row['message']['confidence']),battle_id=bid)
            e.evidence[0].source_type='C_automatic_video_message';e.evidence[0].details.update(timestamp=row['timestamp'],image=row['image'])
            e.attributes.update(fusion_context=True,observation_time=row['timestamp']);events.append(e.to_dict())
    return events


def replay_prefixes(bid,queries,mode,oldparser):
    import tracking.evidence_fusion as fusion
    original=fusion.EventParser
    if mode=='A_controlled':fusion.EventParser=oldparser
    events=input_events(bid)
    if mode=='A_controlled':events=[e for e in events if not any(s['source_type']=='C_automatic_video_message' for s in e['evidence'])]
    initial=BattleState(bid)
    if mode=='M232':
        payload=json.loads((ROOT/f'reports/battles/{bid}/M2.3.2-video-state.json').read_text());initial=from_dict(payload['initial_state']);events=[r['event'] for r in payload['history']]
    # All held-out HUD frame hashes removed, including preceding evaluated
    # checkpoints. This prevents a later persistence check using its earlier label.
    fixture=json.loads(FIXTURE.read_text());held=[r for r in fixture['hud_checkpoints'] if r['battle_id']==bid]
    if mode=='current_persistence':held=[max(held,key=lambda r:r['timestamp'])]
    excluded={r['sha256'] for r in held}
    if mode=='M232' and any(h in json.dumps(initial.to_dict()) for h in excluded):initial=BattleState(bid)
    events=[deepcopy(e) for e in events if not any(oid in excluded for s in e['evidence'] for oid in s['observation_ids']) and event_time(e)<=max(queries)]
    events.sort(key=lambda e:(event_time(e),0 if e['event_type']=='hud_observation' else 1,e['event_id']))
    engine=StateEngine(initial);hidden=HiddenEngine();hidden.seed(engine.initial.to_dict());results={str(t):dict(state=initial.to_dict(),hidden=hidden.projection()) for t in queries}
    for i,e in enumerate(events,1):
        e['attributes']['sequence']=i;engine.history.append(EventRecord(e,i,ordering(event_from_dict(e))))
    def capture(record,state):
        e=deepcopy(record.bindings.get('resolved_event',record.event))
        if e['event_type']=='hud_observation' and record.bindings.get('identity'):e['actor']=deepcopy(record.bindings['identity'])
        hidden.apply(e,instance_id=record.bindings.get('actor',{}).get('pokemon_instance_id'),side=e['side'],sequence=record.delivery_index,application_status=record.application_status)
        for t in queries:
            if event_time(record.event)<t:results[str(t)]=dict(state=state.to_dict(),hidden=hidden.projection())
    began=time.perf_counter()
    try:engine.replay(snapshot_callback=capture)
    finally:fusion.EventParser=original
    seconds=time.perf_counter()-began
    return dict(excluded_frame_hashes=sorted(excluded),prefixes=results,seconds=seconds,events=len(events),status_counts=dict(collections.Counter(r.application_status for r in engine.history)),peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def classify(actual,expected):return 'missing_or_unresolved' if actual is None else 'correct' if actual==expected else 'incorrect'


def hud_score(label,state):
    rows=[]
    for slot in label['slots']:
        pid=state['sides'][slot['side']]['active_slots'].get(slot['slot']);p=state['pokemon'].get(pid,{})
        sid=(p.get('species',{}).get('value') or {}).get('species_id')
        hp=p.get('hp',{});observed=hp.get('displayed_percent',{}).get('value') if 'percent' in slot['hp'] else None
        if 'percent' in slot['hp']:
            # Percent observations are stored separately from exact current HP.
            obs=[o for o in hp.get('observations',[]) if o.get('unit')=='displayed_percent']
            observed=obs[-1]['after'] if obs else None
            expected=slot['hp']['percent']
        else:
            observed=(hp.get('current',{}).get('value'),hp.get('maximum',{}).get('value'))
            if observed==(None,None):observed=None
            expected=(slot['hp']['current'],slot['hp']['maximum'])
        rows.append(dict(side=slot['side'],slot=slot['slot'],instance_id=pid,expected_species=slot['species_id'],species=sid,identity=classify(sid,slot['species_id']),hp=classify(observed,expected),actual_hp=observed,expected_hp=expected,attributed_hp=classify(observed,expected) if sid==slot['species_id'] else 'missing_or_unresolved' if sid is None else 'incorrect'))
    return rows


def main():
    preserve(True);labels=json.loads(FIXTURE.read_text());old=legacy_parser();report=dict(intervals=[interval_score(i,old) for i in labels['intervals']],battles={},fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
    for i in range(5):
        bid=f'sample_battle_{i}';hud=[r for r in labels['hud_checkpoints'] if r['battle_id']==bid];extra=[r for r in labels['supplemental'] if r['battle_id']==bid];queries=sorted({r['timestamp'] for r in hud+extra})
        if bid in INTERVALS:queries += [INTERVALS[bid][1]]
        outputs={}
        for mode in ['M232','A_controlled','current','current_persistence']:
            path=ROOT/f'.cache/battles/{bid}/m233c/replay-{mode}.json'
            identity=fingerprint(dict(mode=mode,fixture=report['fixture_sha256'],code={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/evaluate_m233c.py','battle_events/parser.py','tracking/evidence_fusion.py','tracking/state_engine.py','tracking/hidden_state.py']},events=fingerprint(input_events(bid))))
            if path.exists() and json.loads(path.read_text()).get('input_hash')==identity:value=json.loads(path.read_text())
            else:
                print(bid,mode,'prefix replay',flush=True);value=replay_prefixes(bid,queries,mode,old);value['input_hash']=identity;atomic_json(path,value)
            outputs[mode]=value
        scores={mode:[dict(timestamp=r['timestamp'],slots=hud_score(r,value['prefixes'][str(r['timestamp'])]['state'])) for r in hud] for mode,value in outputs.items()}
        report['battles'][bid]=dict(scores=scores,replay_cost={k:dict(seconds=v['seconds'],events=v['events'],peak_rss_bytes=v['peak_rss_bytes']) for k,v in outputs.items()})
    atomic_json(ROOT/'.cache/m233c/results.json',report);print('Saved C semantic results')
if __name__=='__main__':main()
