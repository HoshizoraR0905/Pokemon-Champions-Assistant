"""Spatially bounded UI counter observations, separate from actual effect duration."""
from copy import deepcopy
import re
from speed_inference.domains import digest

ROI=(265,26,562,154)
LABELS={'下雨状态':'rain','沙暴状态':'sandstorm','大晴天状态':'sun','晴天状态':'sun','下雪状态':'snow',
        '顺风状态':'tailwind','戏法空间状态':'trick_room','戏法空间':'trick_room','青草场地状态':'grassy',
        '精神场地状态':'psychic','薄雾场地状态':'misty','电气场地状态':'electric','光墙状态':'light_screen','反射壁状态':'reflect'}
SEMANTICS={'rain':dict(interpretation='remaining',elapsed_mapping='displayed_denominator - displayed_numerator',
    possible_totals=[5,8],source='User first-hand gameplay observation; Sample Battle 8 opening rain at119.503 followed by5/5 at122.003 before any live move corroborates elapsed0'),
    'trick_room':dict(interpretation='remaining',elapsed_mapping='displayed_denominator - displayed_numerator',possible_totals=[5],
        source='Existing duration-rules-v1 policy plus B9 activation195.017; command counters4/5 at201.017,3/5 at270.028,2/5 at341.007; independent local command segments197.017→253.527→342.008 corroborate decrements'),
    'tailwind':dict(interpretation='remaining',elapsed_mapping='displayed_denominator - displayed_numerator',possible_totals=[4],
        source='Existing duration-rules-v1 policy plus B7 activation message561.028 and UI3/4 at602.002→2/4 at666.012 across independent local boundary659.012; side remains unknown without separate binding') }


def parse_counter(raw,*,source_id,timestamp,bounds,confidence,image=None):
    """A fraction alone, PP/HP, arbitrary locations and fuzzy labels cannot qualify."""
    text=re.sub(r'\s+','',raw)
    if not (ROI[0]<=bounds[0]<bounds[2]<=ROI[2] and ROI[1]<=bounds[1]<bounds[3]<=ROI[3]):return None
    m=re.fullmatch(r'(我方|对手|对方)?('+ '|'.join(sorted(map(re.escape,LABELS),key=len,reverse=True))+r')[:：]?(\d{1,2})/(\d{1,2})',text)
    if not m:return None
    side,label,n,d=m.groups();n=int(n);d=int(d)
    if not 0<=n<=d<=20 or d==0:return None
    effect=LABELS[label];scope='self' if side=='我方' else 'opponent' if side in ('对手','对方') else 'unknown' if effect in ('tailwind','light_screen','reflect') else 'field'
    return dict(id='counter:'+digest([source_id,bounds,raw]),effect=effect,scope=scope,raw_text=raw,
        raw_display=f'{n}/{d}',displayed_numerator=n,displayed_denominator=d,displayed_remaining=None,
        revealed_total_duration=None,inferred_elapsed_turns=None,semantics='unverified',source_id=source_id,
        timestamp=timestamp,bounds=list(bounds),image=image,ocr_confidence=confidence,temporal_confirmation=False,
        origin='spatially_bounded_OCR',active_observation=True)


class CounterTimeline:
    def __init__(self,*,semantics=None):
        self.semantics=deepcopy(SEMANTICS if semantics is None else semantics)
        self.observations=[];self.groups={};self.seen={};self.constraints=[];self.issues=[]

    def consume(self,observation):
        o=deepcopy(observation);oid=o['id'];fingerprint=digest(o)
        if oid in self.seen:
            if self.seen[oid]!=fingerprint:raise ValueError('Counter revision requires explicit replay')
            return dict(status='duplicate_ignored')
        if self.observations and o['timestamp']<self.observations[-1]['timestamp']:raise ValueError('Counters require chronological order')
        self.seen[oid]=fingerprint;key=(o['scope'],o['effect']);group=self.groups.setdefault(key,[])
        n=o['displayed_numerator'];d=o['displayed_denominator'];rule=self.semantics.get(o['effect'])
        o['possible_actual_totals']=None;o['possible_actual_remaining']=None;o['extension_revealed']=False
        if rule and rule['interpretation']=='remaining' and d in rule['possible_totals']:
            elapsed=d-n;totals=[v for v in rule['possible_totals'] if v>=d and v>=elapsed]
            if group and group[-1].get('extension_revealed') and d<group[-1]['displayed_denominator']:
                o['cycle_status']='possible_reactivation_or_OCR_conflict'
            revealed=(d>min(rule['possible_totals']))
            o.update(semantics='remaining',semantic_evidence=deepcopy(rule),displayed_remaining=n,
                inferred_elapsed_turns=elapsed,revealed_total_duration=d if revealed or len(rule['possible_totals'])==1 else None,
                possible_actual_totals=totals,possible_actual_remaining=sorted({v-elapsed for v in totals}),extension_revealed=revealed)
        # Confirmation is causal: the earlier raw record is never overwritten by a later read.
        recent=[p for p in group if 0<=o['timestamp']-p['timestamp']<=4 and p['source_id']!=o['source_id']
            and (p['displayed_numerator'],p['displayed_denominator'])==(n,d) and p['ocr_confidence']>=.9]
        o['temporal_confirmation']=bool(recent and o['ocr_confidence']>=.9)
        o['confirmation_sources']=[p['id'] for p in recent]
        o['track_epoch']=group[-1]['track_epoch'] if group else 1
        if group and o['semantics']=='remaining' and group[-1]['semantics']=='remaining':
            previous=group[-1];step=elapsed-previous['inferred_elapsed_turns']
            if step<0:
                o['track_epoch']+=1;o['cycle_status']='reactivation_or_inconsistent_counter; timeline_link_withheld'
            elif previous.get('cycle_status') is None and o.get('cycle_status') is None:
                self.constraints.append(dict(before=previous['id'],after=o['id'],effect=o['effect'],scope=o['scope'],
                    elapsed_delta=step,frame_interval=[previous['timestamp'],o['timestamp']],
                    qualification='one progression constraint, not invented individual turns' if step>1 else 'counter_elapsed_relation',
                    confirmed=o['temporal_confirmation'] and previous['ocr_confidence']>=.9))
        group.append(o);self.observations.append(o);return deepcopy(o)

    def as_of(self,timestamp):
        result=[]
        for key,group in sorted(self.groups.items()):
            available=[o for o in group if o['timestamp']<=timestamp]
            if available:
                o=deepcopy(available[-1]);o['current_at_query']=o['timestamp']==timestamp
                # An older observation is not a certified current countdown.
                if not o['current_at_query']:
                    o['last_observed_remaining_support']=o['possible_actual_remaining'];o['possible_actual_remaining']=None
                result.append(o)
        return result


def reconcile_segments(segments,counters,effect_events=()):
    """Independent command-anchor counter constraints; never manufacture turns."""
    result=deepcopy(segments)
    for s in result:
        for (scope,effect),group in counters.groups.items():
            if scope!='field':continue
            anchors=[]
            for t in (s['command_start_time'],s['next_command_time']):
                action_times=[e['timestamp'] for e in effect_events if e.get('kind')=='action' and e.get('timestamp') is not None and e['timestamp']>t]
                limit=min(action_times) if action_times else t+4
                reads=[o for o in group if t<=o['timestamp']<limit and o['temporal_confirmation'] and o['semantics']=='remaining']
                anchors.append(reads[0] if reads else None)
            a,b=anchors
            if not a or not b:continue
            restarted=any(e.get('kind')=='effect' and e.get('effect')==effect and e.get('change') in ('start','replace','end','expire')
                and a['timestamp']<e['timestamp']<=b['timestamp'] for e in effect_events if e.get('timestamp') is not None)
            if restarted or a['track_epoch']!=b['track_epoch']:
                s['counter_evidence'].append(dict(before=a['id'],after=b['id'],effect=effect,status='activation_or_counter_epoch_changed; no elapsed relation'))
                continue
            delta=b['inferred_elapsed_turns']-a['inferred_elapsed_turns']
            relation=dict(before=a['id'],after=b['id'],effect=effect,elapsed_delta=delta,
                status='corroborates_one_turn' if delta==1 else 'conflicts_with_one_turn',bounds=[a['timestamp'],b['timestamp']])
            s['counter_evidence'].append(relation)
            if delta!=1:
                s['status']='ambiguous';s['reasons'].append('independent_counter_conflict')
    return result
