"""Read-only 89-row audit. Decisions reflect agent inspection of saved pixels.
No recognition/state policy edits or benchmark prediction writes.
"""
import csv,json
from pathlib import Path
from collections import Counter
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.event_report import verify_seal
from recognition.video_sampling import atomic_json
OWNER=BattleArtifacts('sample_battle_16');RUN='b16-auto-eval-20261026-v1';AUDIT='b16-full-audit-20261027-v1'
read=lambda p:json.loads(p.read_text())

def write_csv(path,rows):
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 source=OWNER.cache('event-driven/'+RUN);cache=OWNER.cache('evaluation/'+AUDIT);out=OWNER.report('evaluation/'+AUDIT);out.mkdir(parents=True,exist_ok=True)
 ref=read(OWNER.cache('evaluation/'+RUN+'/auto-reference/reference.json'));rep=read(source/'replay.json');obs=read(source/'observations.json')['observations'];hs={h['event']['event_id']:h for h in rep['history']}
 old=list(csv.DictReader(OWNER.report('evaluation/'+RUN+'/event_validation.csv').open(encoding='utf-8-sig')));matches={x['reference_id']:x for x in old if x['reference_id']}
 robs={o['observation_id']:(o,v) for v in ref['views'] for o in v['observations']}
 # Explicit audit windows derive from live message anchors, never log-view times.
 hp={12:('opponent',1018,100,13,190,205),19:('opponent',279,100,68,230,249),24:('opponent',1018,19,25,255,261),28:('opponent',279,68,37,280,287),30:('opponent',279,37,62,285,290),32:('opponent',445,100,67,281,297),41:('self',3,129,84,337,353),45:('self',3,84,0,354,371),77:('opponent',279,62,33,665,684),80:('self',279,90,0,680,692),83:('opponent',6,100,0,714,724),87:('self',6,164,12,714,734)}
 raw={5:175.01333333333332,8:186.515,22:253.51,34:299.5,36:305.00166666666667,55:441.0083333333333,61:530.0066666666667,65:603.5183333333333,66:605.0183333333333,68:609.52,69:611.52,75:674.53}
 rows=[]
 for i,e in enumerate(ref['entries'],1):
  match=matches[e['entry_id']];records=[hs[match['prediction_id']]] if match['prediction_id'] else []
  if i in {1,2}:
   records=[h for h in rep['history'] if h['event']['event_type']=='send_out' and abs(h['event']['attributes']['observation_time']-(122.50333333333333 if i==1 else 126.505))<.01]
  if i==54:records=[h for h in rep['history'] if h['event']['event_type']=='weather_change' and abs(h['event']['attributes']['observation_time']-439.00666666666666)<.01]
  category='D';reason='日志像素支持事件；全量实时事件及visual输出未找到对应事件。不能以天气/HP后果反推已识别特性/道具激活。';extra=[];semantic=False;binding=[]
  if records:
   statuses={h['application_status'] for h in records}
   if 'deferred' in statuses:category='B';reason='事件文字/主体可匹配；原状态引擎拒绝应用：'+','.join(str(h['reason']) for h in records)
   elif statuses=={'recorded_observation'}:
    category='B';reason='语义事件存在，但仅写入全局observations；未绑定该效果的实例/目标或更新相应效果状态。归入B的recognized-only子类，不冒称machine deferred。'
   else:category='A';reason='事件顺序、角色与规范语义吻合；原receipt和绑定实例支持应用。'
   semantic=True
   if any(h['application_status']=='applied_partial' for h in records):reason+=' applied_partial只确认该日志行声称的招式执行/成员记录；不声称目标、伤害或全部招式效果已重建。'
   binding=[h['bindings'] for h in records]
  if i in raw:
   r=min(obs,key=lambda x:abs(x['timestamp']-raw[i]));extra=[dict(source_id=r['source_id'],image=r['image'],timestamp=r['timestamp'],raw=r['message']['raw_text'],occurrence_decision=r['occurrence_decision'])]
   category='C';semantic=False;reason='对应实时OCR观察存在，但语义事件未被发出（provisional_or_repeat / 不支持的语义）；C表示检测到了文字却未正确结构化，不等同于实例归属错误。'
   if i==5:reason+=' OCR把进化石Y识为丫；原截图可读Y。'
  if i in hp:
   side,sid,before,after,lo,hi=hp[i];candidates=[]
   for h in rep['history']:
    ev=h['event'];t=ev['attributes']['observation_time'];pid=h['bindings'].get('actor',{}).get('pokemon_instance_id');mon=rep['state']['pokemon'].get(pid,{})
    if ev['event_type']!='hud_observation' or ev['side']!=side or not lo-45<=t<=hi:continue
    if (mon.get('species',{}).get('value') or {}).get('species_id')!=sid:continue
    value=(ev['attributes'].get('hp') or {}).get('value');value=value.get('current') if isinstance(value,dict) else value
    if value in {before,after}:candidates.append((t,value,h,pid))
   pairs=[(a,b) for a in candidates for b in candidates if a[0]<b[0] and a[1]==before and b[1]==after and a[3]==b[3] and lo<=b[0]<=hi]
   if pairs:
    a,b=min(pairs,key=lambda pair:pair[1][0]-pair[0][0]);records=[a[2],b[2]];binding=[h['bindings'] for h in records];category='A';semantic=True
    reason=f'同一绑定实例的HUD先后读取{before}→{after}并应用，顺序与行动窗口一致；不要求日志文本出现在实时消息中，不推断伤害来源。'
   else:
    records=[c[2] for c in candidates[-2:]];category='D';semantic=False
    reason=f'完整HP变化{before}→{after}未重建：在该行动窗口和同一实例内找不到先后两个精确端点；原输出仅保留部分HUD值。'
    if after==0:reason+=' 已查看实时归零截图，画面有0而原输出缺少0；另有faint不等于HP终点已读取。'
    else:reason+=' 可匹配后值，但前值未在该入场实例中获得支持；不能从入场或同种旧实例复制HP。'
   extra += [dict(image=min(obs,key=lambda x:abs(x['timestamp']-t))['image'],timestamp=t) for t in ([366.51166666666666] if i==45 else [690.5] if i==80 else [720.005] if i==83 else [])]
  o,v=robs[e['selected_observation_id']]
  predicted_ids=[h['event']['event_id'] for h in records]
  rows.append(dict(index=i,log_id=e['entry_id'],turn=e['turn'],log_order=e['log_order'],log_text=e['raw_text'],truth_evidence=json.dumps(dict(image=v['image'],sha256=o['frame_sha256'],box=[200,o['box'][1],1111,o['box'][3]],agent_pixel_review=True,inspection_timestamp=v['timestamp'],original_action_timestamp=None),ensure_ascii=False),
   predicted_event_ids=json.dumps(predicted_ids),primary_outcome=category,semantic_supported=semantic,
   state_application_status=json.dumps([h['application_status'] for h in records]),live_timestamps=json.dumps([h['event']['attributes']['observation_time'] for h in records]),
   instance_attribution=json.dumps(binding,ensure_ascii=False),extra_evidence=json.dumps(extra,ensure_ascii=False),reason=reason,
   verification_limit='日志像素经agent查看；实时绑定/receipt为原机器输出核对，非独立人工准确率标注。'))
 assert len(rows)==89 and len({r['log_id'] for r in rows})==89
 write_csv(out/'all_89_records.csv',rows);counts=Counter(r['primary_outcome'] for r in rows)
 ops=[json.loads(line) for line in (OWNER.cache('evaluation/'+RUN+'/profiler/segment-0000/operations.jsonl')).read_text().splitlines()]
 replays=[o for o in ops if o['module']=='state_reconstruction'];rr=[]
 for i,r in enumerate(replays,1):
  inside=[o for o in ops if r['execution_start']<=o['execution_start'] and o['execution_end']<=r['execution_end']]
  ev=[o for o in inside if o['module']=='state_event'];hashes=[o for o in inside if o['module']=='state_hash'];rr.append(dict(index=i,events=len(ev),hash_calls=len(hashes),replay_seconds=r['inclusive_seconds'],hash_seconds=sum(o['exclusive_seconds'] for o in hashes),state_event_exclusive_seconds=sum(o['exclusive_seconds'] for o in ev),execution_start=r['execution_start'],latest_source_time=max((o.get('source') or {}).get('timestamp',0) or 0 for o in ev)))
 write_csv(out/'replay_calls.csv',rr)
 b16=read(source/'manifest.json');comparison=[]
 runtime={13:(251.486,.299),14:(166.015,.244),15:(367.280,.441)}
 # Use the actual frozen benchmark summary values, not a new performance run.
 for n in [13,14,15]:
  old=read(BattleArtifacts(f'sample_battle_{n}').cache('event-driven/fresh-heldout-20261026-v1/manifest.json'))
  changed=sorted(k for k in set(old['identity']['sources'])|set(b16['identity']['sources']) if old['identity']['sources'].get(k)!=b16['identity']['sources'].get(k))
  duration=old['decoder']['container_duration_seconds'];cli,log=runtime[n]
  comparison.append(dict(battle=n,video_seconds=duration,normal_cli_seconds=cli,log_seconds=log,published_combined_seconds=cli+log,normal_PTR=cli/duration,published_PTR=(cli+log)/duration,profiler=False,changed_runtime_sources=changed,
   identical_settings={k:old['identity'].get(k)==b16['identity'].get(k) for k in ['version','config','ocr_manifest','icon_index','identity_mode','icons']}))
 profile=read(OWNER.cache('evaluation/'+RUN+'/profiler/segment-0000/profiler.json'))
 summary=dict(counts={k:counts[k] for k in 'ABCDEF'},A=counts['A'],AB=counts['A']+counts['B'],ABC=counts['A']+counts['B']+counts['C'],denominator=89,performance=comparison,replay_count=len(rr),replayed_events=sum(x['events'] for x in rr),prefix_seconds=sum(x['replay_seconds'] for x in rr[:-1]),final_seconds=rr[-1]['replay_seconds'],prefix_events=sum(x['events'] for x in rr[:-1]),final_events=rr[-1]['events'],direct_measured_profiler_overhead=profile['measured_recording_overhead_seconds'])
 atomic_json(out/'summary.json',summary)
 verify_seal(source)
 atomic_json(out/'audit-manifest.json',dict(status='complete',script_sha256=digest(Path(__file__)),source_prediction_sha256=digest(source/'replay.json'),reference_sha256=digest(OWNER.cache('evaluation/'+RUN+'/auto-reference/reference.json')),outputs={n:digest(out/n) for n in ['all_89_records.csv','replay_calls.csv','summary.json']},policy='agent source-pixel audit plus unchanged machine receipts; original annotations untouched'))
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
