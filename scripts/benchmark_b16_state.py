"""Sealed live-run extraction and independent, pixel-reviewed state benchmark.

Reference stage never loads predictions or imports EventParser. Comparison uses
chronological identity/semantic matching and actual StateEngine snapshots.
"""
import argparse
from collections import Counter,defaultdict
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib,json,re,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from recognition.fast_video import digest
from recognition.event_report import verify_seal
OWNER=BattleArtifacts('sample_battle_16');RUN='b16-semantic-state-20261027-v1'
LIVE=OWNER.cache('event-driven/'+RUN)
OUT=OWNER.cache('evaluation/'+RUN+'/state-benchmark')
REPORT=OWNER.report('evaluation/'+RUN)
ANNOTATIONS=ROOT/'tests/fixtures/battles/sample_battle_16/log_reference_v1.json'

def read(p):return json.loads(p.read_text())
def now():return datetime.now(timezone.utc).isoformat()

def extract():
 import cv2
 from recognition.fast_video import CachedOCR
 from recognition.fast_profile import RegionGate
 from recognition.battle_log import detect_log,extract_view,assemble_views
 verify_seal(LIVE);OUT.mkdir(parents=True,exist_ok=True)
 identity=dict(video_sha256=digest(OWNER.video()),sample_fps=2,model=digest(ROOT/'.cache/m15-onnx-medium/local-manifest.json'),
  dependencies={p:digest(ROOT/p) for p in ['recognition/battle_log.py','recognition/onnx_ocr.py']},version='independent-original-video-log-v1')
 manifest=OUT/'extraction-manifest.json'
 if manifest.exists():
  prior=read(manifest)
  if prior['identity']!=identity:raise ValueError('Reference extraction inputs changed')
  if prior['status']=='complete':return
 began=time.perf_counter();counts=Counter();ocr=CachedOCR(OUT/'log-ocr',counts);views=[]
 state=dict(status='running',identity=identity,started_at=now(),prediction_seal=read(LIVE/'video-only-seal.json'),completed_frames=0)
 atomic_json(manifest,state)
 from recognition.fast_video import decoded_frames
 try:
  for image,metadata in decoded_frames(OWNER.video(),OUT/'reference-decode.log',sample_fps=2.):
   t=metadata['timestamp'];i=round(metadata['target_timestamp']*2)
   row=dict(timestamp=t,source_id=f'tests/fixtures/sample_battle_16.mp4#{t:.6f}')
   row['image']=str((OUT/'log-pixels'/f'{i:06d}.png').relative_to(ROOT))
   path=OUT/'log-views'/f'{i:06d}.json'
   if path.exists():view=read(path)
   else:
    view=None
    if detect_log(image):
     imagepath=ROOT/row['image'];imagepath.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(imagepath),image);row['sha256']=digest(imagepath)
     ocr.source=row['source_id'];ocr.timestamp=row['timestamp'];ocr.gate=RegionGate(.004)
     view=extract_view(image,ocr,row['source_id'],row['timestamp'],row['sha256']);view['image']=row['image']
    atomic_json(path,view)
   if view:views.append(view)
   if i%100==0:
    state.update(completed_frames=i+1,views=len(views),counts=dict(counts));atomic_json(manifest,state)
    print('Independent original-video log extraction',i+1,'sampled frames; views',len(views),flush=True)
  entries,issues=assemble_views(views,ignore_partial_overlap=True)
  observations={r['observation_id']:(r,v) for v in views for r in v['observations']}
  for i,e in enumerate(entries,1):
   row,view=observations[e['selected_observation_id']]
   e.update(index=i,partial=row['partial'],inspection_timestamp=view['timestamp'],original_action_timestamp=None,
    pixel_evidence=dict(image=view['image'],frame_sha256=row['frame_sha256'],box=[200,row['box'][1],1111,row['box'][3]],
     selected_observation_id=row['observation_id'],all_observation_ids=e['observation_ids']))
  atomic_json(OUT/'log-extraction.json',dict(entries=entries,views=views,assembly_issues=issues,
   scanned_sampled_frames=i+1,shared_ocr=True,shared_semantic_parser=False,whole_log_completeness=False))
  state.update(status='complete',completed_frames=i+1,views=len(views),entries=len(entries),issues=len(issues),
   elapsed_seconds=time.perf_counter()-began,counts=dict(counts),output_sha256=digest(OUT/'log-extraction.json'),finished_at=now())
  atomic_json(manifest,state);verify_seal(LIVE)
 except BaseException as exc:
  state.update(status='failed',error=repr(exc));atomic_json(manifest,state);raise

def contacts():
 import cv2
 from PIL import Image,ImageDraw
 raw=read(OUT/'log-extraction.json');entries=raw['entries']
 for base in range(0,len(entries),15):
  sheet=Image.new('RGB',(1000,15*100),'white');draw=ImageDraw.Draw(sheet)
  for j,e in enumerate(entries[base:base+15]):
   proof=e['pixel_evidence'];img=cv2.imread(str(ROOT/proof['image']));x1,y1,x2,y2=proof['box']
   crop=Image.fromarray(cv2.cvtColor(img[y1:y2,x1:x2],cv2.COLOR_BGR2RGB));crop.thumbnail((910,82))
   sheet.paste(crop,(85,j*100+15));draw.text((4,j*100+20),f"#{e['index']} T{e['turn']}\nrow{e['log_order']}",fill='black')
  path=OUT/'pixel-review'/f'log-{base+1:03d}.png';path.parent.mkdir(parents=True,exist_ok=True);sheet.save(path)
  print(path)


def hud_extract():
 """Independent original-video pixel checks, after live sealing; no OCR/state."""
 import cv2
 verify_seal(LIVE);OUT.mkdir(parents=True,exist_ok=True)
 path=OUT/'hud-reference-frames.json'
 if path.exists():return
 from recognition.fast_video import decoded_frames
 frames=[]
 for t in [366.51166666666666,690.5,720.005]:
  checkpoint=OUT/'hud-pixels'/f'source-{round(t*1000)}.json'
  if checkpoint.exists():frames.append(read(checkpoint));continue
  checkpoint.parent.mkdir(parents=True,exist_ok=True)
  decoder=decoded_frames(OWNER.video(),checkpoint.with_suffix('.log'),start=t,end=t+.08,sample_fps=2.)
  try:img,metadata=next(decoder)
  finally:decoder.close()
  target=checkpoint.with_suffix('.png');cv2.imwrite(str(target),img)
  frame=dict(image=str(target.relative_to(ROOT)),sha256=digest(target),requested_timestamp=t,
   source_timestamp=metadata['timestamp'],capture_metadata=metadata,source_video=str(OWNER.video().relative_to(ROOT)),
   provenance='original video separately decoded after seal; prior audit navigation hints; agent must inspect pixels')
  atomic_json(checkpoint,frame);frames.append(frame)
 atomic_json(path,dict(frames=frames,created_at=now()))
 print(json.dumps(frames,indent=2))


def reference():
 # Agent-authored annotations come from fresh log pixels; source identity is
 # resolved through the existing KB, never through live events or parser output.
 from knowledge import KnowledgeBase,normalize
 raw=read(OUT/'log-extraction.json');labels=read(ANNOTATIONS)
 sealed=OUT/'reference-seal.json'
 if sealed.exists():
  frozen=read(OUT/'reference-facts.json')
  if read(sealed)['sha256']!=digest(OUT/'reference-facts.json') or frozen['annotation_sha256']!=digest(ANNOTATIONS) or frozen['extraction_sha256']!=digest(OUT/'log-extraction.json'):
   raise ValueError('Sealed reference changed; preserve it and use a new evaluation namespace')
  hudlabels=read(ANNOTATIONS.with_name('hud_reference_v1.json'))
  frozen_hud={f['fact_id']:f for f in frozen['facts'] if f['reference_source']=='hud'}
  if any(any(frozen_hud.get(f'hud:{i}',{}).get(k)!=v for k,v in claim.items()) for i,claim in enumerate(hudlabels['facts'])):
   raise ValueError('Sealed HUD labels changed')
  print('Reused sealed independent reference',len(frozen['facts']),'facts');return
 if labels['extraction_sha256']!=digest(OUT/'log-extraction.json'):raise ValueError('Wrong annotation evidence')
 entries=labels.get('curated_entries',raw['entries'])
 assert len(labels['records'])==len(entries)
 kb=KnowledgeBase()
 def canonical(name,kind):
  hits=kb.exact[kind].get(normalize(name),[]);ids={e.canonical_id for e in hits}
  if len(ids)!=1:raise ValueError((kind,name,ids))
  return next(iter(ids))
 facts=[];checkpoints=[];episodes=defaultdict(int);active={};unresolved=[]
 for e,label in zip(entries,labels['records']):
  if label['index']!=e['index'] or label['text']!=e['raw_text']:raise ValueError('Annotation row/text mismatch')
  if label.get('unresolved'):
   unresolved.append(dict(index=e['index'],reason=label['unresolved'],evidence=e['pixel_evidence']));continue
  for j,claim in enumerate(label['claims']):
   f=deepcopy(claim);side=f.get('side');sid=f.get('species_id');key=(side,sid)
   if f['category']=='switching' and f['action']=='send_out':
    episodes[key]+=1;active[key]=episodes[key]
   if sid:
    f['episode']=active.get(key)
    if f['episode'] is None:f['identity_limit']='Log subset lacks entry/continuity evidence; evaluate named side/species only'
   if f.get('move'):f['canonical_id']=canonical(f['move'],'move')
   if f.get('ability'):f['canonical_id']=canonical(f['ability'],'ability')
   if f.get('item'):f['canonical_id']=canonical(f['item'],'item')
   f.update(fact_id=f"log:{e['index']}:{j}",log_index=e['index'],turn=e['turn'],log_order=e.get('reference_log_order',e['log_order']),
    reference_source='battle_log',evidence=deepcopy(e['pixel_evidence']),original_action_timestamp=None)
   facts.append(f)
   # Explicit independently supported fields only. No absent/unknown values are
   # scored as false/none; qualitative announcements have no numeric HP field.
   fields=[];category=f['category']
   if category=='move_execution':fields=[('executed_move',f['canonical_id'])]
   elif category in {'damage','healing'}:
    fields=[('hp_before',f['before']),('hp_after',f['after']),('observed_change',f['after']-f['before'])]
   elif category=='ability_activation':fields=[('ability_activation',f['canonical_id'])]
   elif category=='item_activation':fields=[('item_activation',f['canonical_id'])]
   elif category=='weather':fields=[('weather_kind',f['weather'] if f['active'] else 'none'),('weather_active',f['active'])]
   elif category in {'tailwind','terrain','trick_room'}:
    fields=[('effect_active',f['active'])]
    if category=='terrain':fields.append(('terrain_kind',f['terrain']))
    if f.get('active'):fields.append(('effect_onset',True))
   elif category=='status':fields=[('major_status',f['status'])]
   elif category=='qualitative_damage':fields=[('qualitative_damage',f.get('cause'))]
   elif category=='stat_stages':fields=[('stat_direction',f['direction'])]
   elif category=='switching':fields=[('occupancy',f['action']),('instance_species',sid)]
   elif category=='mega_evolution':fields=[('transformation_completed',True)]
   elif category=='protective_effects':fields=[('protection_outcome',f['effect'])]
   elif category=='other_effects' and f['effect']!='mega_stone_reaction_notice':fields=[('scoped_outcome',f['effect'])]
   for field,value in fields:
    checkpoints.append(dict(checkpoint_id=f['fact_id']+':'+field,event_fact_id=f['fact_id'],category=category,field=field,
     expected=value,reference_source='battle_log',evidence=f['evidence']))
   if category=='switching' and f['action'] in {'switch_out','faint'}:active.pop(key,None)
 hudpath=ANNOTATIONS.with_name('hud_reference_v1.json')
 if hudpath.exists():
  hudlabels=read(hudpath)
  if hudlabels['frames_sha256']!=digest(OUT/'hud-reference-frames.json'):raise ValueError('Wrong HUD evidence')
  for i,claim in enumerate(hudlabels['facts']):
   f=deepcopy(claim);f.update(fact_id=f'hud:{i}',category='hp_observation',reference_source='hud',log_index=None)
   facts.append(f)
   checkpoints.append(dict(checkpoint_id=f['fact_id']+':hp_current',event_fact_id=f['fact_id'],category='hp_observation',field='hp_current',expected=f['value'],reference_source='hud',evidence=f['evidence']))
 result=dict(status='sealed',built_at=now(),method='agent annotations of fresh log source pixels; independent from EventParser and live predictions; not human ground truth',
  extraction_sha256=digest(OUT/'log-extraction.json'),annotation_sha256=digest(ANNOTATIONS),facts=facts,checkpoints=checkpoints,unresolved=unresolved,
  limitations=['Shared ONNX OCR and log geometry; pixel review mitigates but does not eliminate correlated errors.',
   'Log viewing timestamps are not action times. No target or damage cause supplied by adjacency.',
   'Species/side/entry episode identity; log does not independently establish screen-left/right occupancy.',
   'No unobserved durations, exact stage baseline or X/Y Mega form inferred.'],
  unavailable_categories=['move_target','numeric_stat_stage','weather_termination','trick_room','terrain','exact_mega_variant','damage_to_move_attribution'],
  source_classes=dict(Counter(f['reference_source'] for f in facts)))
 atomic_json(OUT/'reference-facts.json',result)
 atomic_json(OUT/'reference-seal.json',dict(sealed_at=now(),sha256=digest(OUT/'reference-facts.json')))
 print('Reference sealed',len(facts),'event facts',len(checkpoints),'state fields','unresolved',len(unresolved))


def signature(f,e):
 """Semantic/order match only; never compare raw strings or log view times."""
 k=e['event_type'];a=e.get('attributes',{});cat=f['category']
 kinds={'move_execution':'move_execution','ability_activation':'ability_activation','item_activation':'item_activation',
  'weather':'weather_change','tailwind':'side_condition_change','status':'status_change','stat_stages':'stat_change',
  'qualitative_damage':'hp_change','mega_evolution':'transformation','switching':f.get('action'),'other_effects':'move_effect'}
 if cat=='protective_effects':
  if f['effect']=='wide_guard_established':return k=='side_condition_change' and a.get('condition')=='wide_guard' and a.get('change')=='start'
  return k=='move_effect' and a.get('effect')==f['effect']
 if cat=='other_effects' and f['effect'].startswith('effectiveness:'):
  return k=='effectiveness' and a.get('effect')==f['effect'].split(':')[1]
 if k!=kinds.get(cat):return False
 if cat in {'move_execution','ability_activation','item_activation'}:
  kind={'move_execution':'move','ability_activation':'ability','item_activation':'item'}[cat]
  return (e.get('canonical_references',{}).get(kind) or {}).get('canonical_id')==f['canonical_id']
 if cat=='weather':return a.get('weather')==f['weather'] and a.get('change')==('start' if f['active'] else 'end')
 if cat=='tailwind':return a.get('condition')=='tailwind' and a.get('change')==('start' if f['active'] else 'end')
 if cat=='qualitative_damage':return k=='hp_change' and a.get('qualitative_only') and a.get('direction')=='down' and a.get('cause')==f.get('cause')
 if cat=='status':return a.get('status')==('sleep' if f['status']=='none' else f['status']) and a.get('change')==f['change']
 if cat=='stat_stages':return f['stat'] in a.get('stats',[]) and a.get('direction')==f['direction']
 if cat=='other_effects':return a.get('effect')==f['effect']
 return True


def align_facts(facts,histories):
 """Weighted chronological matching with unordered same-capture groups.

 A mask prevents reusing an event, while reference-order DP allows either
 within-frame serialization order. Different capture times remain ordered.
 """
 fs=[f for f in facts if f['category'] not in {'damage','healing','hp_observation'}]
 excluded={'hud_observation','preview_observation','entry_observation','coverage_observation','trainer_observation','phase_observation','command_checkpoint'}
 hs=[h for h in histories if h['event']['event_type'] not in excluded]
 groups=[];last=None
 for position,h in enumerate(hs):
  t=h['event'].get('attributes',{}).get('observation_time')
  key=('capture',t) if t is not None else ('delivery',position)
  if groups and key==last:groups[-1].append(h)
  else:groups.append([h]);last=key
 def score(f,h):
  e=h['bindings'].get('resolved_event') or h['event']
  if not signature(f,e):return 0
  value=10
  if f.get('side'):value+=4 if e['side']==f['side'] else -2 if e['side']=='unknown' else -7
  if f.get('species_id'):
   actor=e.get('actor') or (e.get('target') if e['event_type']=='effectiveness' else None) or {}
   sid=actor.get('species_id');value+=4 if sid==f['species_id'] else -2 if sid is None else -7
  return value
 n=len(fs);previous=[0]*(n+1);layers=[]
 for group in groups:
  k=len(group)
  if k>12:raise ValueError('Too many simultaneous semantic events to disambiguate conservatively')
  size=1<<k;d=[[-10**9]*size for _ in range(n+1)];parents=[[None]*size for _ in range(n+1)]
  for i in range(n+1):d[i][0]=previous[i];parents[i][0]=('prior',i)
  for i in range(1,n+1):
   weights=[score(fs[i-1],h) for h in group]
   for mask in range(size):
    if d[i-1][mask]>d[i][mask]:d[i][mask]=d[i-1][mask];parents[i][mask]=(i-1,mask,None)
    for j,w in enumerate(weights):
     bit=1<<j
     if mask&bit and w>0 and d[i-1][mask^bit]+w>d[i][mask]:
      d[i][mask]=d[i-1][mask^bit]+w;parents[i][mask]=(i-1,mask^bit,j)
  masks=[max(range(size),key=lambda mask:d[i][mask]) for i in range(n+1)]
  previous=[d[i][masks[i]] for i in range(n+1)];layers.append((group,parents,masks))
 matches={};i=n
 for group,parents,masks in reversed(layers):
  mask=masks[i]
  while True:
   parent=parents[i][mask]
   if parent[0]=='prior':i=parent[1];break
   pi,pm,j=parent
   if j is not None:matches[fs[i-1]['fact_id']]=group[j]['event']['event_id']
   i,mask=pi,pm
 return matches


def compare():
 from tracking.state_engine import StateEngine,EventRecord,ApplicationPolicy
 from tracking.battle_state import from_dict
 verify_seal(LIVE)
 frozen_sources=read(LIVE/'manifest.json')['identity']['sources']
 changed=[p for p,sha in frozen_sources.items() if digest(ROOT/p)!=sha]
 if changed:raise ValueError(('Production sources changed since cold run',changed))
 ref=read(OUT/'reference-facts.json');seal=read(OUT/'reference-seal.json')
 if seal['sha256']!=digest(OUT/'reference-facts.json'):raise ValueError('Reference seal mismatch')
 destination=OUT/'comparison-manifest.json'
 identity=dict(live=digest(LIVE/'replay.json'),reference=seal['sha256'],script=digest(Path(__file__)))
 if destination.exists() and read(destination).get('identity')==identity and read(destination)['status']=='complete':return
 previous_proof=read(destination) if destination.exists() else {}
 atomic_json(destination,dict(status='running',identity=identity,started_at=now()))
 replay=read(LIVE/'replay.json');histories=replay['history'];byid={h['event']['event_id']:h for h in histories}
 matches=align_facts(ref['facts'],histories);byevent=defaultdict(list)
 for f in ref['facts']:
  if f['fact_id'] in matches:byevent[matches[f['fact_id']]].append(f)
 projections={};hp=[]
 def snapshot(record,state):
  eid=record.event['event_id'];event=record.bindings.get('resolved_event') or record.event
  if record.event['event_type']=='hud_observation':
   pid=record.bindings.get('actor',{}).get('pokemon_instance_id');mon=state.pokemon.get(pid)
   binding=record.bindings.get('hud',{})
   if mon and binding.get('hp_status') in {'accepted','accepted_percent'}:
    unit='absolute' if binding['hp_status']=='accepted' else 'displayed_percent'
    value=mon.hp.current.value if unit=='absolute' else mon.hp.displayed_percent.value
    hp.append(dict(event_id=eid,pid=pid,side=mon.side_id,species_id=mon.species.value.get('species_id'),
     time=event['attributes']['observation_time'],value=value,unit=unit,state_hash=record.state_hash,sequence=record.delivery_index))
  if eid not in byevent and event['event_type'] in {'hud_observation','preview_observation','entry_observation','coverage_observation','trainer_observation','phase_observation','command_checkpoint'}:return
  pid=record.bindings.get('actor',{}).get('pokemon_instance_id');mon=state.pokemon.get(pid)
  projection=dict(event_id=eid,sequence=record.delivery_index,source_time=event['attributes'].get('observation_time'),
   application_status=record.application_status,reason=record.reason,bindings=deepcopy(record.bindings),state_hash=record.state_hash,
   weather=asdict(state.weather),sides={s:dict(active_slots=dict(t.active_slots),conditions={k:asdict(v) for k,v in t.conditions.items()}) for s,t in state.sides.items()},
   pokemon=asdict(mon) if mon else None)
  projections[eid]=projection
 cachepath=OUT/'live-checkpoint-projections.json'
 cached=read(cachepath) if cachepath.exists() else {}
 proof=previous_proof
 expected_ids={h['event']['event_id'] for h in histories if (h['bindings'].get('resolved_event') or h['event'])['event_type'] not in {'hud_observation','preview_observation','entry_observation','coverage_observation','trainer_observation','phase_observation','command_checkpoint'}}
 reusable=(cached.get('source_replay_sha256')==identity['live'] and expected_ids<=set(cached.get('projections',{})) and
  proof.get('status')=='complete' and proof.get('outputs',{}).get('live-checkpoint-projections.json')==digest(cachepath))
 if reusable:
  projections=cached['projections'];hp=cached['hp']
  print('Reused verified read-only semantic checkpoints; no StateEngine replay',flush=True)
 else:
  engine=StateEngine(from_dict(replay['initial_state']),ApplicationPolicy(**replay['policy']),mechanic_rules=__import__('tracking.mechanic_rules',fromlist=['MechanicRules']).MechanicRules(**replay['mechanic_rules']))
  engine.history=[EventRecord(**deepcopy(h)) for h in histories]
  def callback(record,state):
   original=byid[record.event['event_id']]
   if record.state_hash!=original['state_hash'] or record.application_status!=original['application_status'] or record.reason!=original['reason']:
    raise ValueError(('Read-only checkpoint differs from sealed receipt',record.event['event_id']))
   snapshot(record,state)
   if record.delivery_index%100==0:print('Evaluation read-only replay',record.delivery_index,'/',len(histories),flush=True)
  engine.replay(snapshot_callback=callback)
  if json.loads(json.dumps(engine.state.to_dict()))!=replay['state']:raise ValueError('Read-only replay differs from sealed state')
  atomic_json(OUT/'live-checkpoint-projections.json',dict(projections=projections,hp=hp,source_replay_sha256=identity['live']))
 # Bind each reference entry episode through a corresponding chronological
 # live send-out, without using the live roster to construct reference identities.
 episodes={}
 for f in ref['facts']:
  if f['category']=='switching' and f['action']=='send_out' and f['fact_id'] in matches:
   h=byid[matches[f['fact_id']]];pid=h['bindings'].get('actor',{}).get('pokemon_instance_id')
   if pid:episodes[(f['side'],f['species_id'],f['episode'])]=pid
 results=[];states=[]
 cps=defaultdict(list)
 for cp in ref['checkpoints']:cps[cp['event_fact_id']].append(cp)
 ordered=sorted([(f['log_index'],byid[eid]['event']['attributes']['observation_time']) for f in ref['facts'] if f['log_index'] is not None and (eid:=matches.get(f['fact_id']))])
 for f in ref['facts']:
  fid=f['fact_id'];eid=matches.get(fid);h=byid.get(eid);actual={};status='missing';reason='No chronological semantic match';pair=None
  pid=episodes.get((f.get('side'),f.get('species_id'),f.get('episode')))
  if f['category']=='hp_observation':
   points=[p for p in hp if p['side']==f['side'] and p['species_id']==f['species_id'] and p['unit']==f['unit'] and abs(p['time']-f['source_time'])<=f.get('sampling_tolerance',.75)]
   found=next((p for p in points if p['value']==f['value']),None)
   if found:
    status='correct_applied';reason='Independent original-video HUD endpoint reproduced';eid=found['event_id'];actual['hp_current']=found['value']
   comparison=dict(fact_id=fid,category=f['category'],status=status,reason=reason,live_event_id=eid,reference_log_index=None,reference_source='hud',reference_source_time=f['source_time'])
  elif f['category'] in {'damage','healing'}:
   lo=max((t for index,t in ordered if index<f['log_index']),default=0)
   hi=min((t for index,t in ordered if index>f['log_index']),default=753.74)
   # A post-action HUD can be sampled just before the next message is read.
   # The reference interval is ordering-only, not a claimed original timestamp.
   points=[p for p in hp if (p['pid']==pid if pid else p['side']==f['side'] and p['species_id']==f['species_id']) and p['unit']==f['unit']]
   pairs=[(a,b) for b in points if lo-1<=b['time']<=hi+1 and b['value']==f['after']
          for a in points if a['pid']==b['pid'] and a['time']<b['time'] and a['value']==f['before']]
   if pairs:
    pair=min(pairs,key=lambda p:p[1]['time']-p[0]['time']);status='correct_applied';reason='Both numeric endpoints in same independently aligned entry episode; no damage attribution'
    actual=dict(hp_before=pair[0]['value'],hp_after=pair[1]['value'],observed_change=pair[1]['value']-pair[0]['value']);eid=pair[1]['event_id']
   else:
    endpoint=next((p for p in points if lo-1<=p['time']<=hi+1 and p['value']==f['after']),None)
    if endpoint:actual['hp_after']=endpoint['value']
    reason='Missing same-instance numeric endpoint pair; faint is not an HP-zero observation'
   comparison=dict(fact_id=fid,category=f['category'],status=status,reason=reason,live_event_id=eid,
    reference_log_index=f['log_index'],reference_source=f['reference_source'],source_window=dict(start=lo,end=hi,basis='neighboring chronological log-event anchors'),
    hp_endpoint_pair=pair,damage_cause=None)
  else:
   if h:
    e=h['bindings'].get('resolved_event') or h['event'];pr=projections.get(eid,{});mon=pr.get('pokemon')
    actual_side=e['side'];actor=e.get('actor') or (e.get('target') if e['event_type']=='effectiveness' else None) or {}
    wrong=f.get('side') and actual_side not in {f['side'],'unknown'} or f.get('species_id') and actor.get('species_id') not in {f['species_id'],None}
    if wrong:status='incorrect';reason='Wrong actor or side'
    elif h['application_status'] in {'applied_candidate','applied_confirmed','applied_partial'}:
     status='correct_applied';reason='Chronological semantic match and applied state receipt'
     if f.get('species_id') and (not mon or f.get('episode') is not None and (pid is None or mon['pokemon_instance_id']!=pid)):
      status='incorrect' if mon and pid else 'recognized_not_applied';reason='Entry-instance binding not established/mismatched'
    else:status='recognized_not_applied';reason=h.get('reason') or h['application_status']
    cat=f['category']
    if mon:
     if cat=='move_execution':
      ids=[m['move']['canonical_id'] for m in mon['moves']['executed'] if m['event_id']==eid]
      if ids:actual['executed_move']=ids[-1]
     elif cat=='status':
      if mon['major_status']['knowledge'] in {'observed','derived'}:actual['major_status']=mon['major_status']['value']
     elif cat in {'ability_activation','item_activation'}:
      observations=mon['ability']['revealed'] if cat=='ability_activation' else mon['item']['activations']
      key='ability' if cat=='ability_activation' else 'item'
      ids=[x[key]['canonical_id'] for x in observations if x['evidence']['event_id']==eid]
      if ids:actual[cat]=ids[-1]
     elif cat=='stat_stages':
      changes=mon['stages'][f['stat']]['changes']
      changes=[c for c in changes if c['evidence']['event_id']==eid]
      if changes:actual['stat_direction']='up' if changes[-1]['change']=='increment' else 'down'
     elif cat=='switching':
      slots=pr['sides'][f['side']]['active_slots'];present=mon['pokemon_instance_id'] in slots.values()
      if present and f['action']=='send_out' or not present and f['action'] in {'switch_out','faint'}:
       actual['occupancy']=f['action']
      actual['instance_species']=(mon['species']['value'] or {}).get('species_id')
     elif cat=='mega_evolution':actual['transformation_completed']=any(t['evidence']['event_id']==eid for t in mon['transformations'])
     elif cat in {'protective_effects','other_effects'}:
      effects=[m['current']['effect']['value'] for m in mon['mechanics'].values() if eid in m['trigger_event_ids'] and m['scope']=='per_action' and 'effect' in m['current']]
      if effects:actual['protection_outcome' if cat=='protective_effects' else 'scoped_outcome']=effects[-1]
     elif cat=='qualitative_damage':
      notices=[o for o in mon['hp']['observations'] if o.get('evidence',{}).get('event_id')==eid
       and o.get('cause')==f.get('cause') and o.get('direction')=='down' and o.get('after') is None]
      if notices and not wrong and pid and mon['pokemon_instance_id']==pid:
       actual['qualitative_damage']=notices[-1]['cause']
       status='correct_applied';reason='Explicit cause notice retained in affected instance HP ledger; numeric amount remains unknown'
    if cat=='weather':
     actual['weather_kind']=pr['weather']['kind']['value'];actual['weather_active']=pr['weather']['active']['value']
    if cat=='tailwind' or cat=='protective_effects' and f.get('effect')=='wide_guard_established':
     effect=pr['sides'].get(f['side'],{}).get('conditions',{}).get('tailwind' if cat=='tailwind' else 'wide_guard',{})
     if effect:
      actual['effect_active']=effect['active']['value'];actual['effect_onset']=(effect['initiated_by'].get('value') or {}).get('event_id')==eid
      if cat=='protective_effects' and actual['effect_active']:actual['protection_outcome']='wide_guard_established'
   comparison=dict(fact_id=fid,category=f['category'],status=status,reason=reason,live_event_id=eid,
    reference_log_index=f['log_index'],reference_source=f['reference_source'],live_application_status=h['application_status'] if h else None,
    live_source_time=h['event']['attributes'].get('observation_time') if h else None)
  results.append(comparison)
  for cp in cps[fid]:
   field=cp['field'];value=actual.get(field);cs='correct_applied' if field in actual and value==cp['expected'] and (status=='correct_applied' or f['category'] in {'damage','healing'}) else \
    'incorrect' if field in actual and value!=cp['expected'] else 'recognized_not_applied' if status=='recognized_not_applied' else 'missing'
   states.append(dict(checkpoint_id=cp['checkpoint_id'],category=cp['category'],status=cs,expected=cp['expected'],actual=value,
    field=field,live_event_id=eid,reference_source=cp['reference_source'],evidence=cp['evidence']))
 def metrics(rows):
  counts=defaultdict(Counter)
  for r in rows:counts[r['category']][r['status']]+=1
  result={k:dict(correct=v['correct_applied'],evaluable=sum(n for s,n in v.items() if s!='unverifiable'),breakdown=dict(v)) for k,v in counts.items()}
  total=Counter(r['status'] for r in rows);den=sum(n for s,n in total.items() if s!='unverifiable')
  return dict(categories=result,overall=dict(correct=total['correct_applied'],evaluable=den,rate=total['correct_applied']/den if den else None,breakdown=dict(total)))
 summary=dict(status='complete',evaluation_type='development/regression; B16 guided fixes',event_facts=metrics(results),state_facts=metrics(states),
  reference_events=len(ref['facts']),reference_state_fields=len(ref['checkpoints']),unresolved_reference=ref['unresolved'],
  qualitative_hp_note='Numeric endpoint facts are reported separately; no actor/move damage causes or targets asserted without independent evidence.',
  unavailable_categories=ref['unavailable_categories'],shared_ocr=True,shared_semantic_parser=False,reference_sealed_before_comparison=True,
  live_replay_identical=True)
 atomic_json(OUT/'event-comparisons.json',results);atomic_json(OUT/'state-comparisons.json',states);atomic_json(OUT/'metrics.json',summary)
 REPORT.mkdir(parents=True,exist_ok=True)
 for name in ['reference-facts.json','event-comparisons.json','state-comparisons.json','metrics.json']:
  atomic_json(REPORT/name,read(OUT/name))
 verify_seal(LIVE);atomic_json(destination,dict(status='complete',identity=identity,finished_at=now(),outputs={n:digest(OUT/n) for n in ['metrics.json','event-comparisons.json','state-comparisons.json','live-checkpoint-projections.json']}))
 print(json.dumps(summary,ensure_ascii=False,indent=2))


def main():
 global RUN,LIVE,OUT,REPORT
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['extract','contacts','hud_extract','reference','compare'])
 p.add_argument('--run-id',default=RUN)
 p.add_argument('--reference-run-id',help='Compare only: reuse sealed reference facts, preserving original output')
 a=p.parse_args()
 from battle_artifacts import canonical_id
 RUN=canonical_id(a.run_id);LIVE=OWNER.cache('event-driven/'+RUN)
 OUT=OWNER.cache('evaluation/'+RUN+'/state-benchmark');REPORT=OWNER.report('evaluation/'+RUN)
 if a.reference_run_id:
  if a.stage!='compare' or a.reference_run_id==RUN:p.error('Reference reuse requires compare and a different run ID')
  source=OWNER.cache('evaluation/'+canonical_id(a.reference_run_id)+'/state-benchmark')
  if read(source/'reference-seal.json')['sha256']!=digest(source/'reference-facts.json'):raise ValueError('Reference seal mismatch')
  OUT.mkdir(parents=True,exist_ok=True)
  for name in ['reference-facts.json','reference-seal.json']:
   target=OUT/name
   if target.exists() and digest(target)!=digest(source/name):raise ValueError('Existing reference differs')
   if not target.exists():target.write_bytes((source/name).read_bytes())
 globals()[a.stage]()
if __name__=='__main__':main()
