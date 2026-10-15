"""Extend the existing offline viewer; frozen M236 and U results stay distinct."""
import hashlib,json,os,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from recognition.video_sampling import atomic_json
from recognition.ui_regions import inspect_ui
from scripts.build_m236_review import receipt
P=ROOT/'.cache/battles/sample_battle_5/m236u';TARGET=ROOT/'reports/M2.3.6-review'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import cv2
    original=P/'previous-review.html';source=original.read_text()
    payload=json.loads(re.search(r'const DATA=(.*?);\nconst \$',source,re.S).group(1))
    baseline_ids={f['id'] for f in payload['frames']};frames={f['id']:f for f in payload['frames']}
    results=[json.loads((P/f'{s}-results.json').read_text()) for s in ['development','held_out']]
    evaluated=json.loads((P/'evaluation.json').read_text())
    replay=json.loads((P/'regression-replay.json').read_text())
    u_receipts=[receipt(r) for r in replay['engine']['history']]
    ui_examples=[]
    for result in results:
        for row in result['frames']:
            u=dict(ui=row['ui'],message=row['message'],baseline=row.get('baseline_message'),
                profile='M2.3.6-U',split=result['split'],
                occurrence=next((d['occurrence'] for d in result['prefix_decisions'] if d['timestamp']==row['timestamp']),None),
                receipts=[r for r in u_receipts if r['timestamp']==row['timestamp']],
                explanation='New visibility/row pipeline; frozen M236 scores remain separate.')
            if row['sha256'] in frames:frames[row['sha256']]['u']=u
            else:
                f=dict(id=row['sha256'],split='u_'+result['split'],timestamp=row['timestamp'],
                    image=os.path.relpath(ROOT/row['image'],TARGET),message=row.get('baseline_message') or dict(raw_text='',confidence=0.),
                    pokemon=[],hud=[],occupancy={},receipts=[],entries=[],scheduling={},visibility_review=None,u=u)
                payload['frames'].append(f);frames[f['id']]=f
            ui_examples.append((frames[row['sha256']],u))
    # Reuse verified full-size status/log layouts without rerunning their OCR.
    visual=json.loads((ROOT/'.cache/m234/visual-results.json').read_text())['results']
    detail=next(r for r in visual if r['request']['kind']=='detail' and r['request']['battle_id']=='sample_battle_3')
    external=[dict(image=detail['request']['image'],timestamp=detail['request']['timestamp'],
                   sha256=sha(ROOT/detail['request']['image']),cached_fields=detail['parsed'],battle_id='sample_battle_3')]
    log_path=ROOT/'reports/M2.1-battle-log-evidence/log-full-374.png'
    if log_path.exists():
        views=json.loads((ROOT/'reports/M2.1-battle-log-raw-ocr.json').read_text())['views']
        view=next((v for v in views if abs(v['timestamp']-374)<1),None)
        external.append(dict(image=str(log_path.relative_to(ROOT)),timestamp=374.,sha256=sha(log_path),
                             cached_fields=dict(observed_at=374.,original_event_time=None,rows=(view or {}).get('observations',[]),
                                                timing='Historical log; opening time is not event occurrence time',new_events_emitted=0),battle_id='sample_battle_2'))
    for row in external:
        ui=inspect_ui(cv2.imread(str(ROOT/row['image'])))
        for region in ui['regions']:
            if region['region_type']==ui['overlay']:region['fields']['cached_extraction']=row['cached_fields']
        f=dict(id=row['sha256'],split='u_layout_regression',timestamp=row['timestamp'],image=os.path.relpath(ROOT/row['image'],TARGET),
               message=dict(raw_text='',confidence=0.),pokemon=[],hud=[],occupancy={},receipts=[],entries=[],scheduling={},visibility_review=None)
        u=dict(ui=ui,message=dict(selected=False,raw_text='',confidence=0.,rows=[]),baseline=None,
               profile='M2.3.6-U',split='layout_regression',receipts=[],battle_id=row['battle_id'],
               explanation='Existing verified cached adapter evidence; no new OCR and no replay event emitted.')
        f['u']=u;payload['frames'].append(f);frames[f['id']]=f;ui_examples.append((f,u))
    labels=dict(party_overlay='Pokémon / Party Overlay',status_overlay='Check Status Overlay',
                battle_log_overlay='Battle Log Overlay',move_description_overlay='Move Description Overlay',
                field_indicator='Weather / terrain / Trick Room indicator',ability_banner='Ability activation banner',
                command_menu='Move / command menu',target_selection='Target-selection overlay')
    for f,u in ui_examples:
        for r in u['ui']['regions']:
            if r['region_type'] not in labels or r['visibility'] not in {'visible','partial'}:continue
            kind=r['region_type'];key='u:'+f['id']+':'+r['region_id']
            payload['events'].append(dict(id=key,title=labels[kind]+' · '+str(round(f['timestamp'],3))+'s',kind=kind,
                split=f['split'],start=f['timestamp'],end=f['timestamp'],frame_ids=[f['id']],
                representatives=dict(before=f['id'],during=f['id'],after=f['id']),priority=6,category='UI layout evidence · '+u['profile'],
                question={'party_overlay':'Which Pokémon and values are visible? Party membership or a selected row is not active-slot evidence.',
                          'status_overlay':'Is the selected subject identifiable? Distinguish current displayed conditions from newly triggered effects.',
                          'battle_log_overlay':'Are these historical log rows readable? Do not assign the overlay-open timestamp to their original events.',
                          'move_description_overlay':'Is this selected-move information? It is not proof of an executed move or an opponent moveset.',
                          'ability_banner':'Which ability and Pokémon label are visible? Screen edge alone does not establish battle side or instance.',
                          'field_indicator':'Read the condition and literal counter. Do not interpret an unverified fraction as remaining turns.'}.get(kind,'Identify the menu before interpreting its text; available choices are not executed actions.'),
                reviewed_occurrence=False,receipts=[],u_category=kind))
    for e in payload['events']:
        if e['id'] in {'occurrence:coaching','occurrence:fake_out'}:e['title']+=' · baseline / U comparison'
    payload['u']=dict(metrics=evaluated['metrics'],cases=evaluated['cases'],new_ocr_predictions=json.loads((P/'ocr-ledger.json').read_text())['total'],
        profile='M2.3.6-U',baseline_frame_count=len(baseline_ids),layout_coverage={
            k:dict(verified_examples=sum(1 for f,u in ui_examples if any(r['region_type']==k and r['visibility']=='visible' for r in u['ui']['regions'])),
                   status='untested: no verified positive' if k=='move_description_overlay' else 'cached examples available') for k in labels},
        caveat='New test: 10 sparse same-recording frames, 3 readable message occurrences, 1 executed move. Existing M236 held-out cases are regressions now.',
        replay_executions=replay['executed_event_receipts'])
    text=(ROOT/'scripts/templates/m236_event_review.html').read_text()
    (TARGET/'review.html').write_text(text.replace('__PAYLOAD__',json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')))
    atomic_json(P/'review-manifest.json',dict(status='complete',renderer=sha(__file__),template=sha(ROOT/'scripts/templates/m236_event_review.html'),
        source_results={str(P/f'{s}-results.json'):sha(P/f'{s}-results.json') for s in ['development','held_out']},
        output=sha(TARGET/'review.html'),cached_frames=len(payload['frames']),ocr_calls=0))
    print('Updated existing viewer with U comparisons and overlay-specific review cards;',len(payload['frames']),'cached images')


if __name__=='__main__':main()
