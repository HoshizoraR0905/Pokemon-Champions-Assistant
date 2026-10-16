"""Portable tests for Battle 6 accounting; no decoding/OCR or labels required."""
from copy import deepcopy

from scripts.report_m237 import coverage_cells, frame_id, turn_segments
from scripts.process_m237 import ScopedArtifacts


def row(t, *, menu=False, text='', selected=False, sha='same-pixels'):
    return dict(timestamp=t, source_id=f'video#{t}', sha256=sha,
                message=dict(selected=selected, raw_text=text),
                ui=dict(regions=[dict(region_id='command', region_type='command_menu', visibility='visible' if menu else 'absent')]))


def test_command_cycle_boundaries_remain_provisional_and_do_not_count_second_selection():
    rows=[row(0),row(10,menu=True),row(10.5,menu=True),row(11),row(12,menu=True),
          row(15,text='move',selected=True),row(16),row(20,menu=True)]
    frozen=deepcopy(rows)
    turns=turn_segments(rows,30)
    assert rows==frozen
    assert [(t['number'],t['start'],t['end']) for t in turns]==[(None,0,10),(1,10,20),(2,20,30)]
    assert all(t['boundary_status']=='provisional' for t in turns if t['number'] is not None)
    assert turns[0]['boundary_status']=='unresolved'


def test_no_command_menu_does_not_invent_turns_or_a_winner():
    turns=turn_segments([row(0),row(5,text='move',selected=True)],10)
    assert len(turns)==1
    assert turns[0]['number'] is None
    assert turns[0]['start']==0 and turns[0]['end']==10


def test_complete_sampling_does_not_establish_event_absence_or_recognition_accuracy():
    rows=[row(t/2) for t in range(20)]
    cells=coverage_cells(rows,10,[])
    assert len(cells)==1 and cells[0]['missing_cells']==[]
    assert cells[0]['status']=='sampled_without_supported_live_message'
    assert cells[0]['absence_of_battle_events_established'] is False
    # High-rate samples in the same cell cannot fill a missing cell.
    missing=coverage_cells([r for r in rows if r['timestamp']!=5]+[row(4.8)],10,[])[0]
    assert missing['missing_cells']==[10]
    assert missing['status']=='insufficiently_sampled'


def test_unresolved_text_is_separate_from_an_emitted_semantic_candidate():
    rows=[row(t/2,text='unresolved' if t==3 else '',selected=t==3) for t in range(20)]
    assert coverage_cells(rows,10,[])[0]['status']=='sampled_unresolved_message_evidence'
    event=dict(event_type='move_execution',attributes=dict(observation_time=2))
    assert coverage_cells(rows,10,[event])[0]['status']=='sampled_with_event_candidates'
    assert not coverage_cells(rows,10,[event])[0]['absence_of_battle_events_established']


def test_same_pixels_at_later_time_keep_distinct_review_ids_and_battle_owned_caches(tmp_path):
    assert frame_id(row(1))!=frame_id(row(2))
    paths=ScopedArtifacts('sample_battle_6',tmp_path)
    assert paths.cache('m235/reads/key.json')==tmp_path/'.cache/battles/sample_battle_6/m237/reads/key.json'
    assert paths.cache('m233b1/sampling/key')==tmp_path/'.cache/battles/sample_battle_6/m237/acquisition/sampling/key'
    assert 'sample_battle_5' not in str(paths.cache('m235/reads/key.json'))


def test_cached_reconstruction_and_delivery_preserve_predictions_and_human_notes(tmp_path, monkeypatch):
    """Exercise adapters/state/report/package together on synthetic unbound evidence."""
    import hashlib
    import json
    from pathlib import Path
    import cv2
    import numpy as np
    from scripts import report_m237 as report
    from battle_artifacts import BattleArtifacts
    from recognition.message_occurrences import MessageOccurrences
    from recognition.video_sampling import atomic_json

    repo=Path(__file__).resolve().parents[1]
    paths=BattleArtifacts('sample_battle_6',tmp_path).prepare()
    cache=paths.cache('m237');cache.mkdir(parents=True)
    output=paths.report('M2.3.7');output.mkdir(parents=True)
    review=output/'review';review.mkdir()
    notes=review/'m237-event-review-annotations.json';notes.write_bytes(b'{"human":"preserve"}')
    image=cache/'synthetic.png';cv2.imwrite(str(image),np.zeros((32,64,3),np.uint8))
    image_sha=hashlib.sha256(image.read_bytes()).hexdigest()
    rows=[];grouping=MessageOccurrences('sample_battle_6');decisions=[]
    for i in range(12):
        r=row(i/2,menu=i<2,text='对手的Synthetic使出了击掌奇袭！' if 3<=i<=5 else '',selected=3<=i<=5,sha=image_sha)
        r['message'].update(confidence=.99,source_region_type='battle_message',rows=[])
        r.update(image=str(image),snapshot={},visual=dict(parsed=[],readings={}),window=[0,6],scheduling=dict(anchor=True))
        r['ui'].update(phase='move_selection' if i<2 else 'battle_screen',overlay=None,profile='synthetic')
        r['ui']['regions'][0].update(bounds=[0,0,64,32],evidence=['synthetic fixture'],fields={},
                                     admission=dict(reason='synthetic UI only'),semantics='available_choices_not_execution')
        rows.append(r)
        d=grouping.observe(r);decisions.append(dict(source_id=r['source_id'],events=[e['event_id'] for e in d['events']]))
    data=dict(observations=rows,occurrences=grouping.groups,roster=[],prefix_decisions=decisions,ocr_cache_hits=0,icon_cache_hits=0)
    atomic_json(cache/'baseline-observations.json',data)
    baseline_bytes=(cache/'baseline-observations.json').read_bytes()
    atomic_json(cache/'baseline-prediction-seal.json',dict(outputs={}))
    atomic_json(cache/'baseline-freeze.json',dict(video=dict(path='synthetic.mp4',metadata=dict(duration_seconds=6,width=64,height=32,fps=2)),video_sha256='synthetic'))
    atomic_json(cache/'protocol.json',dict(sample_fps=2,targeted_fps=3,hud_interval_seconds=2,ocr_budget=100,icon_budget=100))
    for name in ['ocr','icon']:atomic_json(cache/(name+'-ledger.json'),dict(total=0,limit=100,reservations=[]))
    monkeypatch.setattr(report,'ROOT',tmp_path);monkeypatch.setattr(report,'P',cache)
    monkeypatch.setattr(report,'R',output);monkeypatch.setattr(report,'PATHS',paths)
    monkeypatch.setattr(report,'load',lambda name:json.loads((cache/name).read_text()))
    extension=tmp_path/'scripts/templates';extension.mkdir(parents=True)
    (extension/'m237_review_extension.js').write_bytes((repo/'scripts/templates/m237_review_extension.js').read_bytes())
    report.reconstruct()
    result=json.loads((cache/'reconstruction.json').read_text())
    assert result['metrics']['independently_reviewed_events']==0
    assert result['metrics']['correctness_denominator']==0
    assert result['metrics']['correct_actor_bindings'] is None
    assert result['metrics']['outcome']['winner'] is None
    assert len([e for e in result['timeline'] if e['candidate_occurrence']])==1
    assert result['state_prefixes']['initial']['active_slots']=={'self':{},'opponent':{}}
    report.deliver()
    assert notes.read_bytes()==b'{"human":"preserve"}'
    assert (cache/'baseline-observations.json').read_bytes()==baseline_bytes
    html=(review/'review.html').read_text()
    assert 'm237-human-review-v1' in html and 'm236-human-review-v2' not in html
    assert 'first observed command menu' in html
    assert (tmp_path/'reports/M2.3.7-battle-6-full-review.md').resolve()==output/'full-review.md'
    assert len(list((review/'assets').glob('*.png')))==1
    assert 'accuracy unmeasured' in html


def test_later_hp_evidence_never_backfills_an_earlier_move_target():
    from scripts.report_m237 import causal_identity_events
    from recognition.identity_events import events_from_observations
    rows=[]
    for i,text in enumerate(['上吧！龙头地鼠！','对手的班基拉斯使出了岩崩！','龙头地鼠HP100%→70%']):
        rows.append(dict(timestamp=float(i+1),source_id=str(i),sha256=str(i),image='synthetic.png',window=[0,4],
                         message=dict(raw_text=text,confidence=.99)))
    batch=events_from_observations(dict(observations=rows,roster=[]),'synthetic')
    assert next(e for e in batch if e['event_type']=='move_execution')['target'] is not None
    causal=causal_identity_events(rows,[],{'0','1','2'},'synthetic')
    move=next(e for e in causal if e['event_type']=='move_execution')
    assert move['target'] is None and move['attributes']['observation_time']==2
    hp=next(e for e in causal if e['event_type']=='hp_change')
    assert hp['attributes']['observation_time']==3 and hp['side']=='self'
    earlier=causal_identity_events(rows[:2],[],{'0','1'},'synthetic')
    assert move==next(e for e in earlier if e['event_type']=='move_execution')


def test_causal_adapter_preserves_observed_blank_boundary_between_identical_moves():
    from scripts.report_m237 import causal_identity_events
    rows=[]
    for i,text in enumerate(['对手的Synthetic使出了击掌奇袭！','','对手的Synthetic使出了击掌奇袭！']):
        rows.append(dict(timestamp=float(i+1),source_id=str(i),sha256=str(i),image='synthetic.png',window=[0,4],
                         message=dict(raw_text=text,confidence=.99)))
    events=causal_identity_events(rows,[],{'0','2'},'synthetic')
    assert [e['attributes']['observation_time'] for e in events if e['event_type']=='move_execution']==[1,3]


def test_portable_state_projection_keeps_values_and_causal_source_references():
    from scripts.report_m237 import presentation_state
    state=dict(hp=dict(value=93,knowledge='observed',provenance=[dict(event_id='past-event',event_status='candidate',
        sources=[dict(source_type='cached_hud',source_id='video#578',observation_ids=['frame'],
                      details=dict(timestamp=578,sha256='frame',readings={'large':'duplicated OCR tokens'}))])]))
    original=deepcopy(state)
    compact=presentation_state(state)
    assert state==original
    assert compact['hp']['value']==93 and compact['hp']['knowledge']=='observed'
    proof=compact['hp']['provenance'][0]
    assert proof['event_id']=='past-event'
    assert proof['sources'][0]['timestamp']==578
    assert proof['sources'][0]['observation_ids']==['frame']
    assert 'readings' not in str(compact)
