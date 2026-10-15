"""Chronological identity events from observed UI, independent of review labels."""
from copy import deepcopy
from battle_events.schema import BattleEvent,Evidence,stable_id
from battle_events.parser import EventParser


def events_from_observations(data,battle_id):
    from scripts.m232_replay import reconstruct
    # Reuse established message ordering and consecutive-display deduplication.
    messages,_=reconstruct(data,battle_id);events=[];parser=EventParser()
    for row in data.get('roster',[]):
        proof=row['evidence'];t=proof['timestamp']
        events.append(BattleEvent(stable_id(battle_id,'preview:'+proof['sha256']+':'+str(row['preview_row'])),
            'preview_observation','opponent',None,None,'preview UI row',{},None,
            [Evidence('preview_icon',proof['source'],[proof['sha256']],dict(timestamp=t,image=proof['image']))],
            None,'supported',[],dict(battle_id=battle_id,observation_time=t,row=deepcopy(row))).to_dict())
    for row in data['observations']:
        for mon in row.get('snapshot',{}).get('pokemon',[]):
            slot=mon['slot'];side='self' if slot.startswith('own') else 'opponent'
            events.append(BattleEvent(stable_id(battle_id,'hud:'+row['sha256']+':'+slot),'hud_observation',side,None,None,
                'HUD '+mon['species']['raw_text'],{},None,
                [Evidence('cached_hud',row['source_id'],[row['sha256']],dict(timestamp=row['timestamp'],image=row['image']))],
                None,'supported',[],dict(battle_id=battle_id,observation_time=row['timestamp'],slot='left' if slot.endswith('1') else 'right',
                    species=deepcopy(mon['species']),icon=deepcopy(mon.get('icon')),hp=deepcopy(mon.get('hp')))).to_dict())
    for e in messages['video']:
        e['attributes'].pop('sequence',None)
        t=e['evidence'][0]['details']['timestamp'];e['attributes'].update(observation_time=t,fusion_context=True)
        if e['event_type']=='send_out':
            # Preserve arrival even if nickname/species/side/slot is unresolved.
            observed=deepcopy(e);observed['event_id']=stable_id(battle_id,e['event_id']+':entry')
            observed.update(event_type='entry_observation',actor=None,target=None,uncertainty=[],parsing_confidence='supported')
            observed['attributes']=dict(battle_id=battle_id,observation_time=t)
            events.append(observed)
            mentions=parser.species_mentions(e['original_text'])
            if len(mentions)>1 and e['side'] in {'self','opponent'}:
                for i,ref in enumerate(mentions):
                    child=deepcopy(e);child['event_id']=stable_id(battle_id,e['event_id']+':member:'+str(i))
                    child['actor']=ref;child['attributes'].pop('fusion_context',None)
                    child['uncertainty']=[u for u in child['uncertainty'] if u not in {'actor_unresolved','actor_variant_unresolved'}]
                    if ref.get('identity_status')=='species_only':child['uncertainty'].append('actor_variant_unresolved')
                    events.append(child)
                continue
        if e['event_type']=='transformation':
            alias=deepcopy(e);alias['event_id']=stable_id(battle_id,e['event_id']+':alias')
            alias.update(event_type='alias_observation',actor=None,target=None,uncertainty=[],parsing_confidence='supported')
            alias['attributes']=dict(battle_id=battle_id,observation_time=t)
            events.append(alias)
        events.append(e)
    windows=sorted({tuple(r['window']) for r in data['observations']})
    previous=None
    for start,end in windows:
        if previous is not None and start>previous:
            events.append(BattleEvent(stable_id(battle_id,f'gap:{previous}:{start}'),'coverage_observation','field',None,None,
                'unsampled interval',{},None,[Evidence('coverage',battle_id,['gap'],dict(timestamp=start))],None,'supported',[],
                dict(battle_id=battle_id,observation_time=start,start=previous,status='gap',fields=['occupancy'])).to_dict())
        previous=end
    priority={'coverage_observation':0,'preview_observation':1,'hud_observation':2,'entry_observation':3,'alias_observation':4}
    return sorted(events,key=lambda e:(e['attributes']['observation_time'],priority.get(e['event_type'],5),e['event_id']))
