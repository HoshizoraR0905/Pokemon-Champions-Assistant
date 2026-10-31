"""Reviewed per-occurrence B23 alignment. No OCR, decoding or StateEngine replay."""
from collections import Counter
import json
import re
from audit import ROOT, BENCH, PROD, OUT, read, sha, sealed
from recognition.video_sampling import atomic_json

# Fixed after independent reference freeze. Two opening send-out rows and two
# multi-recipient stage notices require two receipts each. No receipt reuse.
ALIGNMENT = '''
1:11,12 2:14,15 3:18 4:19,20 5:255 6:256 7:257 9:261 10:262 11:263
12:442 13:443 14:444 15:445 16:446 18:453 19:458 20:459 21:469 22:473 24:477 26:481
27:576 28:577 29:578 31:583 32:584 33:585 34:586 36:594 38:601
40:694 41:695 42:696 43:697 44:698 45:699 46:700 47:701 48:702 49:704 50:707 52:711 53:746
54:923 55:- 56:924 58:- 59:935 61:941 62:945 63:950 64:952 65:957 68:970 69:979 70:981 72:986 73:987 74:988,989
75:1254 76:1255 77:1256 78:1257 79:1258 80:1259 81:1260 82:1261 83:1262
'''
HP_ALIGNMENT = {8:0,17:1,23:4,25:5,30:6,35:7,37:9,39:10,51:11,57:12,60:13,66:14,67:15,71:16,84:17}
# Readable log versus live channel wording/OCR differences, individually reviewed.
TEXT_OVERRIDES = {27:'对手的雷丘的雷丘进化石丫和AjayVGC的全一环起了反应！',
                  43:'对于对手的炽焰咆哮虎，好像没有效果......'}
TYPE_OVERRIDES = {22:'hp_change',24:'hp_change',36:'hp_change',38:'hp_change',43:'effectiveness',50:'hp_change'}
ADMITTED = {'applied_candidate','applied_confirmed','applied_partial','recorded_observation'}

def normalized(t):
    return re.sub(r'[\s！!。，.,、…：:（）()]','',t).casefold()


def main():
    refpath=OUT/'log-reference.json'; guard=read(BENCH/'log-reference-freeze.json')
    assert sha(refpath)==guard['sha256']
    for frame in read(BENCH/'log-frame-index.json')['frames']:
        assert sha(ROOT/frame['image'])==frame['sha256']
    reference=read(refpath)['rows']; replay=sealed(PROD/'replay.json')
    projection=sealed(BENCH/'hp-resolutions.json'); history=replay['history']
    alignment={int(row):([] if indices=='-' else list(map(int,indices.split(','))))
               for row,indices in (pair.split(':') for pair in ALIGNMENT.split())}
    assert set(alignment).isdisjoint(HP_ALIGNMENT)
    assert set(alignment)|set(HP_ALIGNMENT)==set(range(1,len(reference)+1))
    rows=[]; hp=[]; used=set(); cursor=-1
    for n,ref in enumerate(reference,1):
        if n in HP_ALIGNMENT:continue
        receipts=[]
        for i in alignment[n]:
            assert i>cursor and i not in used
            h=history[i];e=h['bindings'].get('resolved_event') or h['event']
            assert e['event_type']==TYPE_OVERRIDES.get(n,ref['event_type']),n
            assert normalized(e['original_text'])==normalized(TEXT_OVERRIDES.get(n,ref['text'])),n
            admitted=h['application_status'] in ADMITTED
            if admitted:assert e['side']==ref['side'],n
            attrs=e['attributes']
            receipts.append(dict(index=i,event_id=e['event_id'],type=e['event_type'],side=e['side'],
                actor=e.get('actor'),target=e.get('target'),canonical_references=e['canonical_references'],
                fields={k:attrs[k] for k in ['effect','mechanic','identity','stats','direction','stages',
                    'change','condition','form_unresolved','actor_instance_id'] if k in attrs},
                text=e['original_text'],time=attrs['observation_time'],status=h['application_status'],reason=h['reason']))
            used.add(i);cursor=i
        rows.append(dict(reference_id=ref['reference_id'],turn=ref['turn'],text=ref['text'],
            type=ref['event_type'],matched=bool(receipts) and all(r['status'] in ADMITTED for r in receipts),
            text_difference=n in TEXT_OVERRIDES,receipts=receipts))
    for n,i in HP_ALIGNMENT.items():
        ref=reference[n-1];ep=projection['episodes'][i]
        name,before,pct,after,_=re.fullmatch(r'(.+) HP (\d+)(%?) → (\d+)(%?)',ref['text']).groups()
        before,after=int(before),int(after);unit='displayed_percent' if pct else 'absolute'
        p=replay['state']['pokemon'][ep['affected_instance_id']]
        assert p['original_identity']['value']['name']==name and p['side_id']==ref['side']
        start=ep['source_event']['time'];end=ep['resolution_end']['time']
        numeric=[o for o in p['hp']['observations'] if o.get('unit')==unit]
        def timestamp(o):return o['evidence']['sources'][0]['details']['timestamp']
        previous=[o for o in numeric if timestamp(o)<start]
        obs=previous[-1:]+[o for o in numeric if start<=timestamp(o)<=end]
        pair=next(((a,b) for ai,a in enumerate(obs) for b in obs[ai+1:]
                   if a['after']==before and b['after']==after),None)
        exact=ep['before']==before and ep['after']==after and ep['unit']==unit
        hp.append(dict(reference_id=ref['reference_id'],turn=ref['turn'],text=ref['text'],
            episode_index=i,episode_id=ep['episode_id'],instance_id=ep['affected_instance_id'],
            raw_ordered_endpoints=pair is not None,raw_endpoint_event_ids=[o['evidence']['event_id'] for o in pair] if pair else [],
            exact_projection=exact,complete_endpoints=exact and ep['complete_endpoints'],
            program_supported=exact and ep['attribution_status']=='supported'))
    summary=dict(semantic_records=dict(matched=sum(r['matched'] for r in rows),total=len(rows)),
        move_execution=dict(matched=sum(r['matched'] for r in rows if r['type']=='move_execution'),
                            total=sum(r['type']=='move_execution' for r in rows)),
        matched_receipts=sum(len(r['receipts']) for r in rows if r['matched']),
        per_turn={str(t):dict(matched=sum(r['matched'] for r in rows if r['turn']==t),total=sum(r['turn']==t for r in rows)) for t in range(1,7)},
        hp_total=len(hp),hp={k:sum(r[k] for r in hp) for k in ['raw_ordered_endpoints','exact_projection','complete_endpoints','program_supported']})
    result=dict(reference_sha256=sha(refpath),frozen_inputs={str(p.relative_to(ROOT)):sha(p) for p in [PROD/'replay.json',BENCH/'hp-resolutions.json']},
        method='Reviewed chronological one-to-one accepted message records; not complete semantic/state accuracy.',
        limitations=['Partial visible log only; Codex visual reference without human review.',
            'No original game-turn boundaries verified; reference timestamps are inspection times.',
            'Two reviewed live/log wording differences retained, including Y→丫 OCR error.',
            'Raichu exact Mega form unresolved; stone notices lack canonical item structure.',
            'Accepted move-revelation/observation receipts do not establish applied effects.',
            'No precision, complete six-stat runtime, stage-state or whole-match accuracy measured.'],
        summary=summary,semantic_rows=rows,hp_rows=hp)
    atomic_json(OUT/'log-score.json',result);print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
