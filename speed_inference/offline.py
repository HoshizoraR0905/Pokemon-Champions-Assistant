"""Read-only audit of saved evidence, without StateEngine mutation or video work."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import tempfile
from .domains import configuration_space, digest
from .posterior import SpeedBelief

RUNS={5:'m238-rc-b5-v1',6:'m238-switch-continuity-v2',7:'production-first-pass-v1',
      8:'m239-production-first-pass-v1',9:'m24-development-final-v1'}


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name)
    try:
        with os.fdopen(fd,'w') as f:json.dump(value,f,ensure_ascii=False,sort_keys=True,allow_nan=False,indent=2);f.write('\n')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def audit_payload(battle_id,events,replay,*,metadata=None):
    """Announcement adjacency is diagnostic only; saved bindings do not verify turns."""
    if replay['state']['battle_id']!=battle_id:raise ValueError('Replay battle ownership mismatch')
    bindings={h['event']['event_id']:h for h in replay['history']}
    moves=[]
    for e in events:
        declared=e.get('attributes',{}).get('battle_id')
        if declared and declared!=battle_id:raise ValueError('Event battle ownership mismatch')
        if e['event_type']!='move_execution':continue
        h=bindings.get(e['event_id'],{});b=h.get('bindings',{})
        a=e.get('attributes',{});actor=e.get('actor') or {};m=e.get('canonical_references',{}).get('move') or {}
        sources=[dict(source_type=s.get('source_type'),source_id=s.get('source_id'),observation_ids=s.get('observation_ids',[]),
            timestamp=s.get('details',{}).get('timestamp')) for s in e.get('evidence',[])]
        moves.append(dict(event_id=e['event_id'],occurrence_id=a.get('occurrence_id'),side=e.get('side'),
            timestamp=a.get('observation_time'),actor=actor.get('canonical_id'),actor_name=actor.get('name'),
            instance_binding=b.get('actor'),move=m.get('canonical_id'),move_name=m.get('name'),sources=sources,
            parsing_confidence=e.get('parsing_confidence'),uncertainty=e.get('uncertainty'),
            delivery_order=h.get('ordering'),application_status=h.get('application_status'),
            exclusion_reasons=['same_turn_unverified','order_decision_snapshot_missing','own_unmodified_speed_missing',
                'priority_and_hidden_modifiers_unverified','Champions_ordering_not_independently_certified']+
                (['actor_instance_binding_missing'] if not b.get('actor',{}).get('pokemon_instance_id') else [])+
                (['move_identity_missing'] if not m.get('canonical_id') else [])))
    pairs=[]
    for a,b in zip(moves,moves[1:]):
        if {a['side'],b['side']}=={'self','opponent'}:
            pairs.append(dict(event_ids=[a['event_id'],b['event_id']],timestamps=[a['timestamp'],b['timestamp']],
                eligible=False,reasons=sorted(set(a['exclusion_reasons']+b['exclusion_reasons'])),
                interpretation='Adjacent saved announcements only, not established same-turn action order'))
    subjects=[]
    for pid,p in sorted(replay['state']['pokemon'].items()):
        if p.get('side_id')!='opponent':continue
        current=p.get('current_variant',{});identity=current.get('value')
        subject=dict(instance_id=pid,current_variant=identity,identity_knowledge=current.get('knowledge'),
            identity_evidence_event_ids=[s.get('event_id') for s in current.get('provenance',[])],
            as_of='final_saved_state_only; never back-projected onto earlier actions',
            item_knowledge=p.get('item',{}).get('knowledge'),ability_knowledge=p.get('ability',{}).get('knowledge'))
        if identity is None or current.get('knowledge') not in ('observed','derived'):
            subject.update(status='no_prior',reason='current_form_unresolved; no_base_form_assumption')
        else:
            try:
                model=configuration_space(identity=identity,form='as_named')
                belief=SpeedBelief(model,battle_id=battle_id,instance_id=pid,stat_epoch='final-saved-current-form')
                summary=belief.summary(include_configurations=False)
                subject.update(status='prior_only',prior=summary,posterior=summary,eligible_observations=[],information_gain_nats=0.,
                    prior_parameterization=model['prior'],stat_provenance=model['provenance'])
            except (ValueError,NotImplementedError) as exc:subject.update(status='no_prior',reason=str(exc))
        subjects.append(subject)
    return dict(battle_id=battle_id,metadata=metadata,subjects=subjects,move_announcements=moves,
        diagnostic_adjacent_opposite_side_pairs=pairs,event_count=len(events),move_count=len(moves),eligible_observations=[],
        applied_updates=0,information_gain_nats=0.,final_saved_turn=replay['state'].get('turn'),
        conclusion='No eligible comparison: priors remain unchanged. Recognition receipts and timestamp adjacency do not verify turn/speed context.')


def audit_battle(number,*,root=Path.cwd()):
    if number not in RUNS:raise ValueError('Select one of sample battles 5..9')
    from battle_artifacts import BattleArtifacts
    root=Path(root).resolve()
    battle=BattleArtifacts(f'sample_battle_{number}',root)
    run=battle.cache('event-driven/'+RUNS[number])
    event_path=run/('events.json' if number==6 else 'video-only.json')
    paths=[event_path,run/'replay.json',run/'manifest.json']
    source_hashes={str(p.relative_to(root)):file_hash(p) for p in paths}
    implementation_root=Path(__file__).resolve().parents[1]
    implementation={str(p.relative_to(implementation_root)):file_hash(p) for p in (implementation_root/'speed_inference').rglob('*.py')}
    implementation['battle_artifacts.py']=file_hash(implementation_root/'battle_artifacts.py')
    # Include maintained dependencies in cache validity, not only new adapter files.
    for directory in ('speed_order','knowledge','damage'):
        for p in (implementation_root/directory).rglob('*'):
            if p.is_file() and p.suffix in ('.py','.json'):implementation[str(p.relative_to(implementation_root))]=file_hash(p)
    fingerprint=digest(dict(sources=source_hashes,implementation=implementation,version=1))
    out=battle.cache('m341/'+fingerprint[:16]);manifest=out/'manifest.json';result=out/'audit.json'
    if manifest.exists() and result.exists():
        old=json.loads(manifest.read_text())
        if old.get('status')=='complete' and old.get('fingerprint')==fingerprint and old.get('output_sha256')==file_hash(result):
            return dict(battle_id=battle.battle_id,reused=True,result=str(result))
    state=dict(battle_id=battle.battle_id,status='running',fingerprint=fingerprint,source_hashes=source_hashes,
        implementation=implementation,started_at=datetime.now(timezone.utc).isoformat(),outputs=[str(result)])
    atomic_json(manifest,state)
    try:
        source_manifest=json.loads(paths[2].read_text())
        if source_manifest.get('status')!='complete':raise ValueError('Selected source run is incomplete; reuse successful stages before auditing')
        data=json.loads(event_path.read_text());replay=json.loads(paths[1].read_text())
        if data.get('battle_id')!=battle.battle_id:raise ValueError('Event envelope battle ownership mismatch')
        audit=audit_payload(battle.battle_id,data['events'],replay,metadata=dict(
            game_turn_numbers_verified=data.get('game_turn_numbers_verified'),source_hashes=source_hashes,
            source_limitations=data.get('limitations',[]),run=RUNS[number]))
        atomic_json(result,audit);state.update(status='complete',output_sha256=file_hash(result))
    except Exception as exc:
        state.update(status='failed',error=repr(exc));atomic_json(manifest,state);raise
    atomic_json(manifest,state)
    return dict(battle_id=battle.battle_id,reused=False,result=str(result),event_count=audit['event_count'],
        move_count=audit['move_count'],subjects=len(audit['subjects']),applied_updates=0)
