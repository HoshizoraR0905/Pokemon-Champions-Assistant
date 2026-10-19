"""Replay-owned identity claims; no recognition, probabilities or scene geometry."""
from copy import deepcopy
import re
from battle_events.aliases import alias_key


def trainer_from_opening_hud(engine, state, event, record):
    """Calibrate a named opening entry only when both sides' HUD pairs agree.

    Association becomes available at this HUD timestamp, never at the earlier
    announcement. Literal labels are matched, not party membership or future
    species observations. Existing SideState.trainer owns the resulting claim.
    """
    from .state_engine import evidence_link, event_from_dict
    timestamp = event.attributes['observation_time']
    slots = state.knowledge.get('hud_fusion', {}).get('slots', {})
    pairs = {}
    proofs = []
    for side in state.sides:
        pair = []
        for slot in ('left', 'right'):
            last = slots.get(side + ':' + slot, {})
            sources = last.get('evidence', {}).get('sources', [])
            if (last.get('status') != 'accepted' or last.get('timestamp') != timestamp
                    or not last.get('raw') or not sources
                    or sources[0]['source_id'] != event.evidence[0].source_id):
                return
            pair.append(alias_key(last['raw'])); proofs.append(deepcopy(last['evidence']))
        if len(set(pair)) != 2:
            return
        pairs[side] = set(pair)
    for earlier in engine.history:
        e = earlier.event; a = e.get('attributes', {})
        if (earlier.retracted or earlier.application_status != 'recorded_observation'
                or e['event_type'] != 'entry_observation' or e['side'] != 'unknown'
                or a.get('observation_time', float('inf')) >= timestamp
                or (e.get('ocr_confidence') or 0) < .95):
            continue
        refs = a.get('ordered_display_references', [])
        if len(refs) != 2 or len({alias_key(x) for x in refs}) != 2:
            continue
        # Do not associate an old opening with a later post-action occupancy.
        if any(r.event['event_type'] in {'move_execution', 'switch_out', 'faint', 'transformation'}
               and a['observation_time'] < r.event.get('attributes', {}).get('observation_time', float('inf')) <= timestamp
               and not r.retracted for r in engine.history):
            continue
        match = re.fullmatch(r'(.+?)派出了.+', re.sub(r'\s+', '', e['original_text']))
        if not match or match[1] == '训练家':
            continue
        sides = [side for side, pair in pairs.items() if pair == {alias_key(x) for x in refs}]
        if len(sides) != 1:
            continue
        side = sides[0]; trainer = state.sides[side].trainer
        name = match[1]
        if trainer:
            continue
        other = [team.trainer for s, team in state.sides.items()
                 if s != side and team.trainer.get('display_name') == name]
        if other:
            for claim in other:
                claim['status'] = 'conflicting'
            continue
        state.sides[side].trainer = dict(display_name=name, status='accepted', observed_at=timestamp,
            basis='opening_entry_literal_pair_and_same_frame_accepted_huds',
            evidence=[evidence_link(event_from_dict(e)), *proofs],
            unique_trainer_id=None)
        record.bindings['trainer'] = deepcopy(state.sides[side].trainer)


def remember_alias(state,raw,identity,evidence,*,side,instance_id=None,source='same_hud_independent_icon'):
    ledger=state.knowledge.setdefault('identity_ledger',dict(aliases=[],roster=[],entries=[]))
    claim=dict(battle_id=state.battle_id,side=side,raw_nickname=raw,lookup_key=alias_key(raw),
        identity=deepcopy(identity),evidence=deepcopy(evidence),instance_id=instance_id,
        source=source,status='accepted',alternatives=[],persistent_individual_proven=False)
    prior=[a for a in ledger['aliases'] if a['side']==side and a['lookup_key']==claim['lookup_key']]
    for old in prior:
        if old['identity']['species_id']!=identity['species_id'] or (
                old['raw_nickname']!=raw and old.get('instance_id')!=instance_id):
            old['status']=claim['status']='conflicting'
            claim['alternatives'].append(deepcopy(old['identity']))
    ledger['aliases'].append(claim)
    from .active_continuity import current_episode
    episode=current_episode(state,instance_id)
    if episode:claim['active_episode_id']=episode['episode_id']
    return claim


def entry_visual_support(engine,state,event,*,record=None):
    """Repeated saved icon classifications can support an announced nickname.

    A complete preview restricts candidates, never chooses a species or selected
    party. This does not reconcile command HUDs against authoritative slots.
    """
    from .state_engine import evidence_link, event_from_dict
    from .evidence_fusion import knowledge
    from recognition.event_schedule import entry_slots
    from .active_continuity import current_episode
    if state.knowledge.get('active_continuity_v1') and event.side in state.sides:
        pid=state.sides[event.side].active_slots.get(event.attributes.get('slot'))
        ep=current_episode(state,pid)
        if ep and ep.get('hud_binding'):
            from .entry_hud import support,known_support
            return known_support(state,event) if state.pokemon[pid].species.known else support(state,event)
    a=event.attributes;species=a.get('species') or {};icon=a.get('icon') or {}
    raw=species.get('raw_text') or '';sid=icon.get('species_id')
    if (event.side!='opponent' or a.get('identity_reused_from') or not raw
            or species.get('confidence',0)<.95 or icon.get('status')!='resolved'
            or not sid or not icon.get('candidates') or icon['candidates'][0].get('species_id')!=sid
            or (species.get('resolution') or {}).get('species_id')!=sid
            or (species.get('resolution') or {}).get('method')!='icon_only'):
        return None
    ledger=state.knowledge.setdefault('identity_ledger',dict(aliases=[],roster=[],entries=[]))
    roster=[r for r in ledger['roster'] if r['side']==event.side]
    by_row={}
    for r in roster:by_row.setdefault(r['preview_row'],[]).append(r)
    reliable=(set(by_row)==set(range(1,7)) and all(
        all(r.get('status')=='resolved' and r.get('species_id') for r in rows)
        and len({r['species_id'] for r in rows})==1 for rows in by_row.values()))
    if not reliable or sid not in {r['species_id'] for r in roster}:return None
    timestamp=a['observation_time'];entry=None;single=None
    for h in engine.history:
        if record is not None and (h.ordering is None or record.ordering is None
                or h.ordering['domain']!=record.ordering['domain']
                or tuple(h.ordering['key'])>=tuple(record.ordering['key'])):continue
        e=h.bindings.get('resolved_event',h.event);attrs=e.get('attributes',{});t=attrs.get('observation_time')
        if h.retracted or t is None or t>=timestamp:continue
        if e['event_type']=='move_execution':entry=None
        if e['side']=='unknown' and e['event_type'] in {'switch_out','faint'}:entry=None;single=None
        if e['side']!=event.side:continue
        if e['event_type']=='entry_observation':
            single=None
            refs=attrs.get('ordered_display_references',[])
            slots=entry_slots(event.side,refs)
            matches=[literal for literal,slot in zip(refs,slots) if slot==a['slot']
                     and alias_key(literal).endswith(alias_key(raw))]
            if len(matches)==1:entry=e
            else:entry=None
        elif e['event_type']=='send_out':
            # A single replacement may have an unresolved species but an
            # independently observed trainer side. Later HUDs establish only
            # present occupancy, never an earlier message's application.
            single=None
            refs=attrs.get('ordered_display_references',[])
            if (len(refs)==1 and alias_key(refs[0]).endswith(alias_key(raw))
                    and e.get('ocr_confidence',0) is not None and e['ocr_confidence']>=.95):single=e
        elif e['event_type'] in {'switch_out','faint'}:entry=None;single=None
    prospective=False
    if entry is None and single is not None:
        from .active_continuity import current_episode
        team=state.sides[event.side]
        vacant=set(team.vacant_slots)-set(team.active_slots)
        pid=team.active_slots.get(a['slot']);p=state.pokemon.get(pid);ep=current_episode(state,pid)
        provisional=bool(p and not p.species.known and ep and ep['entry_event_id']==single['event_id'])
        if (vacant=={a['slot']} and a['slot'] not in team.active_slots) or provisional:
            entry=single;prospective=True
    if entry is None:return None
    proof=event.evidence[0]
    if not proof.observation_ids:return None
    frame=proof.observation_ids[0]
    key=(entry['event_id'],a['slot'],alias_key(raw))
    observations=ledger.setdefault('entry_visual_observations',[])
    relevant=[o for o in observations if tuple(o['key'])==key]
    item=dict(key=list(key),species_id=sid,frame=frame,evidence=evidence_link(event),
              icon={k:deepcopy(icon.get(k)) for k in ('status','species_id','method','region')},
              raw_nickname=raw,timestamp=timestamp)
    if not any(o['frame']==frame for o in relevant):observations.append(item);relevant.append(item)
    if len({o['species_id'] for o in relevant})!=1 or len({o['frame'] for o in relevant})<2:return None
    entity=knowledge().entities.get(f'pokeapi:species:{sid}')
    if entity is None:return None
    identity=dict(canonical_id=entity.canonical_id,species_id=sid,kind='species',
                  name=entity.names.get('zh-hans'),knowledge_snapshot=knowledge().snapshot_id,identity_status='species_only')
    return dict(identity=identity,raw_nickname=raw,entry_event_id=entry['event_id'],
        prospective_only=prospective,established_at=timestamp,historical_entry_applied=False,
        raw_sendout=entry['original_text'],selected_party_membership_proven=False,
        evidence=[evidence_link(event_from_dict(entry)),*[o['evidence'] for o in relevant]],
        preview_evidence=[deepcopy(r['evidence']) for r in roster],
        policy='announced_nickname_repeated_independent_frames_preview_membership_v1')


def transition(engine,state,event,record):
    from .state_engine import Contradiction,Deferred,evidence_link
    a=event.attributes
    if not state.knowledge.get('identity_v1'):raise Deferred('identity_profile_required')
    if a.get('battle_id')!=state.battle_id:raise Contradiction('identity_battle_ownership_mismatch')
    ledger=state.knowledge.setdefault('identity_ledger',dict(aliases=[],roster=[],entries=[]))
    if event.event_type=='trainer_observation':
        from recognition.trainers import aggregate_trainer
        trainer=deepcopy(a['trainer'])
        if trainer.get('battle_id')!=state.battle_id or trainer.get('side')!=event.side or event.side not in state.sides:
            raise Contradiction('trainer_ownership_mismatch')
        if (trainer.get('entity_kind')!='trainer' or not trainer.get('evidence')
                or any(p.get('timestamp',float('inf'))>a['observation_time'] for p in trainer.get('evidence',[]))):
            record.bindings['trainer']=dict(status='unresolved',observation=trainer)
            state.observations.append(dict(kind='trainer_identity_unresolved',evidence=evidence_link(event)))
            return True
        previous=state.sides[event.side].trainer
        trainer=aggregate_trainer(previous,trainer)
        trainer.update(observed_at=a['observation_time'])
        state.sides[event.side].trainer=trainer
        record.bindings['trainer']=deepcopy(trainer)
    elif event.event_type=='preview_observation':
        row=deepcopy(a['row'])
        if row.get('battle_id')!=state.battle_id or row.get('side')!=event.side or event.side not in state.sides:raise Contradiction('preview_ownership_mismatch')
        ledger['roster'].append(row);record.bindings['preview']=row
    elif event.event_type=='entry_observation':
        ledger['entries'].append(dict(event_id=event.event_id,side=event.side,
            raw_text=event.original_text,slot=None,species=None,status='unresolved',evidence=evidence_link(event)))
    elif event.event_type=='alias_observation':
        # Only an explicit, same-message species revelation can establish this
        # route. Roster membership alone is not an alias source.
        from battle_events.parser import EventParser
        from .evidence_fusion import knowledge
        parsed=EventParser(knowledge()).parse(dict(entry_id=event.event_id,source_id=event.evidence[0].source_id,
            raw_text=event.original_text,ocr_confidence=event.ocr_confidence),battle_id=state.battle_id)
        if (parsed.event_type!='transformation' or not parsed.attributes.get('identity')
                or event.ocr_confidence is None or event.ocr_confidence<.95 or parsed.side!=event.side):
            raise Deferred('explicit_alias_revelation_unresolved')
        raw=event.original_text.split('超级进化成了',1)[0].strip()
        if raw.startswith('对手的'):raw=raw[len('对手的'):]
        if not raw:raise Deferred('empty_display_alias')
        identity=parsed.attributes['identity']
        # Revelation proves a named episode, without proving its doubles slot or
        # equivalence to a past individual. Do not duplicate a known active one.
        from .battle_state import PokemonState
        from .evidence_fusion import context_supported
        matches={a.get('instance_id') for a in ledger['aliases'] if a['side']==event.side
            and a['status']=='accepted' and a['lookup_key']==alias_key(raw)
            and a['identity']['species_id']==identity['species_id']
            and any(pid==a.get('instance_id') and context_supported(state,event.side,slot,event.attributes['observation_time'])
                for slot,pid in state.sides[event.side].active_slots.items())}
        if len(matches)==1:
            pid=next(iter(matches));p=state.pokemon[pid]
        else:
            pid=state.battle_id+':'+event.side+':alias:'+event.event_id.rsplit(':',1)[-1]
            p=PokemonState(pid,event.side);state.pokemon[pid]=p;state.sides[event.side].party_instance_ids.append(pid)
            engine._assign(p,'location',dict(kind='observed_unplaced',slot=None),event)
        engine._assign(p,'species',identity,event)
        if identity.get('canonical_identity'):engine._assign(p,'current_variant',identity['canonical_identity'],event)
        claim=remember_alias(state,raw,identity,[evidence_link(event)],side=event.side,instance_id=pid,source='explicit_species_revelation')
        record.bindings['alias']=claim
    return True
