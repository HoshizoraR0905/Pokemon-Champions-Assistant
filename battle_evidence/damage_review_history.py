"""Reviewed stage transitions at an admission boundary; not a parallel state engine."""
def stage_history(review,replay):
    history=review.get('stage_history')
    if not history:return None
    by_id={e['id']:e for e in replay['timeline']};value=history['initial_stage'];last=-1;receipts=[]
    for r in history['transitions']:
        e=by_id[r['event_id']]
        if e.get('instance_id')!=review['attacker'] or e['timestamp']>=review['action_time'] or e['timestamp']<last:
            raise ValueError('Stage history actor/chronology mismatch')
        if not set(s['source_id'] for s in e.get('sources',[]))&{s['source_id'] for s in review['sources'].values()}:
            raise ValueError('Stage transition lacks reviewed source')
        last=e['timestamp']
        if r['kind']=='reset':
            if e['kind']!='switch_out':raise ValueError('Stage reset requires switch source')
            value=0
        else:
            if e['kind']!='stat_change' or r['kind']!='delta' or type(r['delta']) is not int:raise ValueError('Reviewed quantitative stat transition required')
            value=max(-6,min(6,value+r['delta']))
        receipts.append(dict(event_id=e['id'],timestamp=e['timestamp'],stage=value))
    supplied={r['event_id'] for r in history['transitions']}
    for e in replay['timeline']:
        if history['since']<e['timestamp']<review['action_time'] and e.get('instance_id')==review['attacker']:
            if e['kind']=='switch_out' and e['id'] not in supplied:raise ValueError('Unreviewed switch resets stage history')
            if e['kind']=='stat_change' and '特攻' in e.get('text','') and e['id'] not in supplied:raise ValueError('Unreviewed Special Attack transition')
    if value!=review['context']['attacker_stages']['special_attack']:raise ValueError('Stage history and action-time stage disagree')
    return dict(stat='special_attack',stage=value,transitions=receipts,basis=history['basis'],unresolved_items=history.get('unresolved_items',[]))
