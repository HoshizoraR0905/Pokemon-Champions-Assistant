"""Offline reference alignment. Nothing here is imported by recognition or state."""
from difflib import SequenceMatcher
from collections import Counter


def compact(text):
    return ''.join(text.split()).rstrip('！!。.')


def similarity(log, event):
    if log['event_type']!='unknown' and event['event_type']!=log['event_type']:return 0.
    lr=log.get('canonical_references',{});er=event.get('canonical_references',{})
    for key,value in lr.items():
        other=er.get(key)
        if value and other and value.get('canonical_id')!=other.get('canonical_id'):return 0.
    literal=SequenceMatcher(None,compact(log['original_text']),compact(event['original_text'])).ratio()
    if literal<.45:return 0.
    # Semantic agreement helps wording differences but never creates a match alone.
    canonical=any(v and er.get(k) and v.get('canonical_id')==er[k].get('canonical_id') for k,v in lr.items())
    return min(1.,literal+(.18 if canonical else 0))


def align(entries, log_events, predictions):
    predictions=[e for e in predictions if e['event_type'] not in {'hud_observation','preview_observation','entry_observation','coverage_observation'}]
    n,m=len(entries),len(predictions)
    scores=[[similarity(a,b) for b in predictions] for a in log_events]
    # Ordered weighted subsequence; skipped video events are unscored because
    # observed log pages are incomplete. No inspection timestamp is a match key.
    dp=[[0.]*(m+1) for _ in range(n+1)]
    for i in range(1,n+1):
        for j in range(1,m+1):
            score=scores[i-1][j-1]
            dp[i][j]=max(dp[i-1][j],dp[i][j-1],dp[i-1][j-1]+score if score>=.72 else -1)
    pairs={};i,j=n,m
    while i and j:
        score=scores[i-1][j-1]
        if score>=.72 and abs(dp[i][j]-(dp[i-1][j-1]+score))<1e-8:
            pairs[i-1]=j-1;i-=1;j-=1
        elif dp[i-1][j]>=dp[i][j-1]:i-=1
        else:j-=1
    comparisons=[]
    for i,(entry,event) in enumerate(zip(entries,log_events)):
        pred=predictions[pairs[i]] if i in pairs else None
        uncertain=[]
        if entry.get('partial') or entry['ocr_confidence']<.9 or event['event_type']=='unknown':
            status='historical_entry_incomplete';reason='Partial, uncertain OCR or unsupported historical row semantics'
        elif pred is None:
            status='missing_logged_event';reason='No sufficiently supported ordered video match; recognition versus routing cause unresolved'
        else:
            score=scores[i][pairs[i]]
            alternatives=[predictions[j]['event_id'] for j,s in enumerate(scores[i]) if s>=score-.03 and j!=pairs[i]]
            for role in ['actor','target']:
                a=event.get(role);b=pred.get(role)
                if a and b and a.get('canonical_id')!=b.get('canonical_id'):uncertain.append('incorrect_'+role)
                elif a and not b:uncertain.append('unresolved_'+role)
            if event['side']!='unknown' and pred['side']!='unknown' and event['side']!=pred['side']:uncertain.append('incorrect_side')
            turn=pred.get('attributes',{}).get('turn')
            if turn is not None and turn!=entry.get('turn'):uncertain.append('incorrect_turn')
            if alternatives:
                status='ambiguous_alignment';reason='Multiple similar occurrences; ordered alignment is provisional'
                uncertain.append(dict(alternative_event_ids=alternatives))
            elif any(s in uncertain for s in ['incorrect_actor','incorrect_target','incorrect_side']):
                status='incorrect_actor_target';reason='Event wording aligns but observed participants differ'
            elif 'incorrect_turn' in uncertain:
                status='wrong_turn';reason='Independently observed turn disagrees'
            else:
                status='provisional_match';reason='Ordered text/semantic agreement; requires human confirmation'
            if turn is None:uncertain.append('video_turn_unknown')
        comparisons.append(dict(log_entry_id=entry['entry_id'],turn=entry.get('turn'),log_text=entry['raw_text'],
            prediction=pred,status=status,reason=reason,uncertainty=uncertain,log_observation_ids=entry.get('observation_ids',[])))
    used={predictions[j]['event_id'] for j in pairs.values()}
    return dict(comparisons=comparisons,unmatched_predictions=[dict(event=e,status='unscored_log_coverage_unknown') for e in predictions if e['event_id'] not in used],
        summary=dict(observed_log_entries=n,status_counts=dict(Counter(c['status'] for c in comparisons)),
            provisional_matches=sum(c['status']=='provisional_match' for c in comparisons),
            missing_logged_events=sum(c['status']=='missing_logged_event' for c in comparisons),
            verified_matches=0,whole_match_coverage=None,warning='Observed log pages are partial. OCR/parser agreement is not independent human correctness.'))
