"""Duration sets advance at evidenced game boundaries, never by video seconds."""
from copy import deepcopy
from pathlib import Path
import json

RULE_POLICY=json.loads((Path(__file__).parent/'duration-rules-v1.json').read_text())

DOCUMENTED={
    'tailwind':dict(turns=[4],source='https://wiki.52poke.com/wiki/顺风',scope='Champions description; inclusive activation turn documented in effect section'),
    'trick_room':dict(turns=[5],source='https://wiki.52poke.com/wiki/戏法空间',scope='Champions description; inclusive activation turn documented in effect section'),
}


class EffectDurations:
    def __init__(self):self.effects={};self.history=[];self.seen=set();self.last_boundary=None

    def consume(self,e,assignment):
        if e['id'] in self.seen:return
        if e.get('source_retracted') or e.get('source_revision_requires_review'):
            self.history.append(dict(event_id=e['id'],effects=self.snapshot(),issue='inactive_source_not_interpreted'));return
        self.seen.add(e['id']);turn=assignment.get('number')
        if e['kind']=='effect':
            effect=e['effect'];scope=e.get('scope');key=(scope,effect)
            if not isinstance(effect,str) or effect=='unknown':
                for row in self.effects.values():
                    if row['family']==e.get('family') and row['scope']==scope:self._uncertain(row)
                self.history.append(dict(event_id=e['id'],turn=turn,effects=self.snapshot(),issue='effect_identity_unresolved'));return
            if scope not in ('field','self','opponent'):
                self.history.append(dict(event_id=e['id'],turn=turn,effects=self.snapshot(),issue='effect_scope_unresolved'));return
            # Weather/terrain replacement ends the previous named effect in the same family.
            family=e.get('family',effect)
            if e['change'] in ('start','replace'):
                for old in self.effects.values():
                    if old['scope']==scope and old['family']==family and old['effect']!=effect:
                        old.update(active=False,remaining_support=[0],status='replaced');old['events'].append(e['id'])
            previous=self.effects.get(key)
            if e['change']=='observe' and previous:
                row=deepcopy(previous)
                if e.get('verified') is True:row['active']=True
            elif e['change'] in ('end','expire','remove','cancel'):
                row=deepcopy(previous) if previous else dict(effect=effect,scope=scope,family=family,activation_event=None,start_turn=None,initial_support=None,rule=None,events=[])
                row.update(active=False if e.get('verified') else None,remaining_support=[0] if e.get('verified') else list(range(max(row.get('remaining_support') or [0])+1)) if row.get('remaining_support') is not None else None,status='observed_expiration' if e['change']=='expire' else 'observed_end')
            elif e['change']=='extend' and previous:
                row=deepcopy(previous);extension=e.get('extension')
                if type(extension) is int and 0<extension<=100 and e.get('duration_verified') and e.get('duration_sources'):
                    row['remaining_support']=[x+extension for x in row['remaining_support']] if row['remaining_support'] is not None else None
                else:row['remaining_support']=None
                row['status']='extended' if row['remaining_support'] is not None else 'extension_duration_unknown'
            else:
                rule=DOCUMENTED.get(effect);initial=None
                if e.get('duration_verified') is True and e.get('duration_sources'):
                    initial=e.get('initial_support');rule=dict(source=e['duration_sources'],scope='explicit documented Champions duration assertion',timing=e.get('decrement_at'))
                elif rule:initial=rule['turns']
                if rule:rule=dict(deepcopy(rule),policy=deepcopy(RULE_POLICY))
                if initial is not None:
                    if not isinstance(initial,list) or not initial or any(type(x) is not int or not 1<=x<=100 for x in initial):raise ValueError('Invalid duration support')
                    initial=sorted(set(initial))
                activation=(e['change'] in ('start','replace') and e.get('verified') is True and turn is not None)
                remaining=initial if activation else list(range(1 if e.get('verified') else 0,max(initial)+1)) if initial else None
                row=dict(effect=effect,scope=scope,family=family,activation_event=e['id'] if e['change'] in ('start','replace') else None,
                    start_turn=turn if activation else None,intra_turn=e.get('intra_turn','unknown'),initial_support=initial,
                    remaining_support=remaining,active=True if e.get('verified') is True else None,
                    status='exact' if activation and initial and len(initial)==1 else 'bounded' if remaining is not None else 'unknown',
                    decrement_at=e.get('decrement_at','turn_end' if effect in DOCUMENTED else None),rule=rule,events=[],ticks=[])
            if e['change'] in ('start','replace'):
                row['activation_timestamp']=e.get('timestamp');row['activation_verified']=e.get('verified') is True
            row['events'].append(e['id']);row['last_event']=e['id'];self.effects[key]=row
        elif e['kind']=='boundary' and turn is not None:
            timing={'start':'turn_start','end':'turn_end'}.get(e.get('boundary'),e.get('boundary'))
            boundary=(turn,timing)
            if boundary!=self.last_boundary:
                for row in self.effects.values():
                    if row['active'] is False:continue
                    if self.last_boundary and (turn>self.last_boundary[0]+1 or turn<self.last_boundary[0]):
                        self._uncertain(row)
                    tick_turn=turn
                    matches=row.get('decrement_at')==timing
                    if timing=='turn_start' and row.get('decrement_at')=='turn_end' and self.last_boundary and self.last_boundary[0]==turn-1:
                        tick_turn=turn-1;matches=True
                    if row.get('start_turn') is not None and matches:
                        if tick_turn in row.get('ticks',[]):continue
                        if timing=='turn_start' and row.get('decrement_at')=='turn_start' and row['start_turn']==turn:continue
                        if tick_turn<row['start_turn']:continue
                        row.setdefault('ticks',[]).append(tick_turn)
                        values=row['remaining_support']
                        if values is not None:
                            row['remaining_support']=sorted({max(0,x-1) for x in values})
                            row['active']=False if row['remaining_support']==[0] else None if 0 in row['remaining_support'] else row['active']
                            row['status']='expired_by_documented_duration' if row['active'] is False else 'exact' if len(row['remaining_support'])==1 else 'bounded'
                        row['events'].append(e['id'])
                self.last_boundary=boundary
        elif turn is None and e['kind'] not in ('effect',):
            for row in self.effects.values():self._uncertain(row)
        self.history.append(dict(event_id=e['id'],turn=turn,effects=self.snapshot()))

    @staticmethod
    def _uncertain(row):
        if row['active'] is False:return
        row['active']=None
        if row['remaining_support'] is not None:row['remaining_support']=list(range(max(row['remaining_support'])+1))
        row['status']='bounded' if row['remaining_support'] is not None else 'unknown'
        row['start_turn']=None

    def advance_visual_boundary(self,segment):
        """Relative, documented effect clock on confirmed contiguous segments only.

        The local clock is separate from the absolute game-turn clock. It never
        backfills an unseen activation or progresses across an uncertain segment.
        """
        if segment['status']!='confirmed':return
        for row in self.effects.values():
            initial=row.get('initial_support');activated=row.get('activation_timestamp')
            if not initial or not row.get('activation_verified') or row.get('active') is False:continue
            if row.get('decrement_at')!='turn_end':continue
            start=segment['command_start_time'];end=segment['next_command_time']
            clock=row.get('visual_clock') or {}
            if segment['id'] in clock.get('segments',[]):continue
            if activated is not None and start<=activated<end:
                support=sorted({max(0,x-1) for x in initial});segments=[segment['id']]
            elif clock.get('through_command_time')==start:
                support=sorted({max(0,x-1) for x in clock['remaining_support']});segments=clock['segments']+[segment['id']]
            else:
                if clock:
                    row['visual_clock']=dict(clock,status='continuity_unverified',remaining_support=list(range(max(clock['remaining_support'])+1)))
                continue
            row['visual_clock']=dict(remaining_support=support,segments=segments,
                through_command_time=end,status='derived_from_documented_duration_and_local_boundaries',
                activation_event=row['activation_event'],numbering_scope='local')
        self.history.append(dict(visual_boundary=segment['id'],effects=self.snapshot()))

    def observe_ui_counter(self,observation):
        """Merge a direct UI observation without changing the activation event/turn."""
        o=deepcopy(observation);key=(o['scope'],o['effect'])
        if o['scope'] not in ('self','opponent','field'):
            self.history.append(dict(counter=o,issue='UI counter side unresolved; not applied to either side'))
            return
        if o['id'] in self.seen:return
        self.seen.add(o['id'])
        row=self.effects.setdefault(key,dict(effect=o['effect'],scope=o['scope'],family=o['effect'],
            activation_event=None,start_turn=None,initial_support=None,remaining_support=None,
            active=None,status='unknown',events=[],rule=None))
        row.setdefault('ui_counter_history',[]).append(o['id'])
        row['ui_counter']=o
        row['ui_remaining_support']=o['possible_actual_remaining']
        # Active visual presence remains an observation, distinct from rule-derived expiry.
        row['ui_active_observation']=True
        row['ui_temporally_confirmed']=o['temporal_confirmation']
        row['ui_counter_timestamp']=o['timestamp']
        self.history.append(dict(counter_id=o['id'],effects=self.snapshot()))

    def snapshot(self):return [deepcopy(v) for k,v in sorted(self.effects.items())]
