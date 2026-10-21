"""Turn identity requires evidence; command windows remain unnumbered candidates."""
from copy import deepcopy
from speed_inference.domains import digest


class TurnReconstruction:
    def __init__(self,battle_id):
        self.battle_id=battle_id;self.turns=[];self.current=None;self.windows=[];self.window=None
        self.visual_segments=[];self.assignment={};self.unassigned=[];self.ledger=[];self.seen={};self.issues=[]

    def consume(self,event):
        e=deepcopy(event);eid=e['id'];fingerprint=digest({k:v for k,v in e.items() if k!='position'})
        if eid in self.seen:
            if self.seen[eid]!=fingerprint:raise ValueError('Evidence revision requires explicit reconstruction')
            return dict(status='duplicate_ignored')
        if e['battle_id']!=self.battle_id:raise ValueError('Cross-battle event')
        self.seen[eid]=fingerprint;self.ledger.append(e)
        if e.get('source_retracted') or e.get('source_revision_requires_review'):
            result=dict(turn_id=None,number=None,status='inactive_source_requires_review',order_verified=False)
            self.assignment[eid]=result;return deepcopy(result)
        proof=e.get('turn_evidence') or {};number=proof.get('number');verified=(proof.get('verified') is True and bool(proof.get('sources')) and type(number) is int and number>0)
        if not verified and self.current and self.current['start'] and not self.current['end']:
            continuity=e.get('turn_continuity',{})
            if continuity.get('verified') is True and continuity.get('sources'):
                proof=dict(number=self.current['number'],verified=True,sources=continuity['sources'],
                    execution_order=continuity.get('execution_order'),execution_order_verified=continuity.get('execution_order_verified'),decision_id=continuity.get('decision_id'))
                number=self.current['number'];verified=True
        boundary=proof.get('boundary')
        if verified:
            if self.turns and number<self.turns[-1]['number']:
                self.issues.append(dict(event_id=eid,reason='turn_number_regression'));verified=False
            else:
                if not self.current or self.current['number']!=number:
                    self.current=dict(id=f'{self.battle_id}:turn:{number}',number=number,numbering_evidence=[],
                        start=None,end=None,status='partial',actions=[],switches=[],state_changes=[],end_of_turn=[],events=[])
                    self.turns.append(self.current)
                t=self.current;t['numbering_evidence'].append(deepcopy(proof));t['events'].append(eid)
                if boundary=='start':
                    if t['start'] is None:t['start']=dict(event_id=eid,timestamp=e.get('timestamp'),interval=proof.get('interval'))
                if boundary=='end':
                    t['end']=dict(event_id=eid,timestamp=e.get('timestamp'),interval=proof.get('interval'))
                t['status']='complete' if t['start'] and t['end'] else 'partial'
        # Numbered membership is never inherited past an unverified gap.
        assigned=self.current if verified and self.current['number']==number else None
        kind=e['kind']
        if kind=='command_window':
            if self.window:self.window['end_bound']=e.get('timestamp')
            self.window=dict(id=f'{self.battle_id}:partial:{eid}',number=None,start_bound=e.get('timestamp'),end_bound=None,
                status='ambiguous_command_window',actions=[],events=[],provenance=e.get('sources'),
                limitation='May span partial or multiple game turns; no one-cycle-one-turn assertion')
            self.windows.append(self.window)
        if assigned:
            if kind=='action':assigned['actions'].append(eid)
            elif kind in ('switch','forced_replacement'):assigned['switches'].append(eid)
            elif kind=='end_of_turn':assigned['end_of_turn'].append(eid)
            elif kind not in ('boundary','command_window'):assigned['state_changes'].append(eid)
            self.assignment[eid]=dict(turn_id=assigned['id'],number=number,status='confirmed_membership',
                order_verified=proof.get('execution_order_verified') is True and type(proof.get('execution_order')) is int,
                execution_order=proof.get('execution_order'),decision_id=proof.get('decision_id'),sources=proof['sources'])
        else:
            self.assignment[eid]=dict(turn_id=None,number=None,status='unassigned',order_verified=False)
            if self.window:
                self.window['events'].append(eid)
                if kind=='action':self.window['actions'].append(eid)
                self.assignment[eid]['candidate_window']=self.window['id']
            if kind=='action':self.unassigned.append(eid)
        return deepcopy(self.assignment[eid])

    def attach_visual(self,segments):
        """Attach locally bounded membership without inventing absolute turn numbers/order."""
        if self.visual_segments:raise ValueError('Visual segments already attached; replay explicitly')
        members=set()
        for segment in segments:
            if segment.get('battle_id')!=self.battle_id:raise ValueError('Cross-battle visual segment')
            if segment['status']!='confirmed':continue
            ids={a['event_id'] for a in segment['actions']}
            if members & ids:raise ValueError('Overlapping visual action membership')
            members.update(ids)
        self.visual_segments=deepcopy(segments)
        for segment in segments:
            if segment['status']!='confirmed':continue
            for action in segment['actions']:
                eid=action['event_id']
                if eid not in self.assignment:continue
                prior=self.assignment[eid]
                if prior.get('status')=='inactive_source_requires_review':continue
                if prior.get('number') is not None:
                    prior['visual_segment_id']=segment['id'];continue
                self.assignment[eid]=dict(prior,turn_id=segment['id'],number=None,
                    status='confirmed_local_membership',numbering_scope='local',sources=segment['frames'],
                    local_segment_index=segment['local_index'],order_verified=False)
                if eid in self.unassigned:self.unassigned.remove(eid)

    def export(self):
        result=dict(battle_id=self.battle_id,visual_segments=deepcopy(self.visual_segments),turns=deepcopy(self.turns),partial_windows=deepcopy(self.windows),
            assignment=deepcopy(self.assignment),unassigned_actions=list(self.unassigned),issues=deepcopy(self.issues),ledger=deepcopy(self.ledger))
        # Store chronological observed order separately from trustworthy execution order.
        for t in result['turns']:
            t['actions_by_verified_execution_order']=sorted(
                [x for x in t['actions'] if self.assignment[x]['order_verified']],key=lambda x:self.assignment[x]['execution_order'])
        return result
