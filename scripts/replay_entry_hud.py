"""Saved-only entry-centric HUD validation; never invokes scene recognition."""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import resource
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json
from scripts.run_production_evaluation import runtime_sources
from tracking.active_continuity import occupancy,current_episode
from tracking.entry_hud import POLICY,display_name
from tracking.battle_state import from_dict
from tracking.evidence_projection import source_times
from tracking.state_engine import StateEngine,EventRecord


def read(p):return json.loads(p.read_text())
def forbidden(*args,**kwargs):raise AssertionError('Saved-entry replay cannot acquire recognition')


def slots(state):
    result={}
    for side,team in state.sides.items():
        for slot in ('left','right'):
            p=state.pokemon.get(team.active_slots.get(slot));ep=current_episode(state,p.pokemon_instance_id) if p else None
            result[side+':'+slot]=dict(occupancy=occupancy(state,side,slot),instance_id=p.pokemon_instance_id if p else None,
                species_id=(p.species.value or {}).get('species_id') if p else None,
                name=(p.species.value or {}).get('name') if p else None,display_reference=ep.get('display_reference') if ep else None,
                arrival=ep['start'] if ep else None,identity_resolution=ep.get('species_resolution_time') if ep else None,
                display_name=display_name(ep) if ep else None,display_name_evidence=deepcopy(ep.get('hud_display_name')) if ep else None,
                episode_id=ep['episode_id'] if ep else None,hud_binding=deepcopy(ep.get('hud_binding')) if ep else None)
    return result


def timeline_html(target,report,timeline,summary,rows):
    images={r['timestamp']:dict(image=os.path.relpath(ROOT/r['image'],report.parent),sha256=r['sha256']) for r in rows}
    data=dict(timeline=timeline,summary=summary,images=images)
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Provisional entry timeline</title>
<style>body{font:16px system-ui;margin:24px;background:#101827;color:#eef}button,select{font:inherit}#time{width:100%}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{background:#213049;padding:16px;border-radius:10px}.occupied_unidentified{border:2px solid #eab54a}.occupied_identified{border:2px solid #53bd9b}.vacant{border:2px solid #778}img{max-width:100%;max-height:55vh}pre{white-space:pre-wrap;overflow-wrap:anywhere}.note{color:#bdcce4}</style>
<h1>Provisional occupancy and prospective identity</h1><p class="note">Saved-evidence diagnostic. Unknown species stay unknown before resolution. Only saved 2D HUD evidence is used. No scene recognition is invoked. Previous first-pass acceptance is unchanged.</p>
<p id="count"></p><input id="time" type="range" min="0" step="1"><select id="event"></select><div id="content"></div><h2>Episode HUD audit</h2><pre id="audit"></pre><div id="probes"></div>
<script>const DATA=__DATA__;
const slider=document.querySelector('#time'),selector=document.querySelector('#event');slider.max=DATA.timeline.length-1;
function node(tag,text){let n=document.createElement(tag);n.textContent=text;return n}
DATA.timeline.forEach((r,i)=>{let o=node('option',r.timestamp.toFixed(6)+'s '+r.type+' '+r.raw.replaceAll('\\n',' '));o.value=i;selector.append(o)});
function render(){let i=Number(slider.value),r=DATA.timeline[i],out=document.querySelector('#content');selector.value=i;out.replaceChildren();out.append(node('h2',r.timestamp.toFixed(6)+'s — '+r.type),node('pre',r.raw),node('p',r.application_status+' · '+r.event_id));let cards=node('div','');cards.className='cards';Object.entries(r.slots).forEach(([k,v])=>{let c=node('div','');c.className='card '+v.occupancy;c.append(node('h3',k),node('strong',v.occupancy),node('p',(v.display_name||v.display_reference||'')+' · species '+(v.species_id??'unknown')),node('p','Message reference: '+(v.display_reference||'unknown')),node('p','Arrival: '+(v.arrival??'unknown')+'s; species resolved: '+(v.identity_resolution??'unknown')),node('pre',v.instance_id||'No current instance'));cards.append(c)});out.append(cards);let source=DATA.images[String(r.timestamp)];if(source){let img=document.createElement('img');img.src=source.image;img.alt='Original saved frame at '+r.timestamp+'s';out.append(img,node('pre','Frame SHA256 '+source.sha256))}document.querySelector('#audit').textContent=JSON.stringify(Object.fromEntries(Object.entries(r.slots).filter(([k,v])=>v.hud_binding).map(([k,v])=>[k,v.hud_binding])),null,2);document.querySelector('#count').textContent=(i+1)+' / '+DATA.timeline.length+' ordered records; '+DATA.summary.recognition_calls+' recognition calls';}
slider.oninput=render;selector.onchange=()=>{slider.value=selector.value;render()};render();
DATA.summary.model_probes.forEach(p=>{let d=node('details','');d.append(node('summary',p.entry_timestamp+'s: '+p.status+' — '+p.reason));p.frames.forEach(f=>{d.append(node('p',f.timestamp+'s · species unknown · no automated prediction'));let im=document.createElement('img');im.src=DATA.images[String(f.timestamp)].image;im.alt='Entry probe frame '+f.timestamp+'s';d.append(im,node('pre',f.sha256))});document.querySelector('#probes').append(d)});
</script></html>'''.replace('__DATA__',payload)
    report.parent.mkdir(parents=True,exist_ok=True);report.write_text(html)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battle',required=True);parser.add_argument('--baseline',required=True)
    parser.add_argument('--diagnostic-id',required=True);parser.add_argument('--frames-run')
    args=parser.parse_args();owner=BattleArtifacts(args.battle);source=owner.cache(args.baseline)
    target=owner.cache('evaluation/'+args.diagnostic_id);report=owner.report('evaluation/'+args.diagnostic_id+'/timeline.html')
    if target.exists() and not (target/'manifest.json').exists():raise ValueError('Preserve occupied namespace')
    target.mkdir(parents=True,exist_ok=True)
    identity=dict(policy=POLICY,baseline=str(source.relative_to(ROOT)),baseline_sha256=digest(source),sources=runtime_sources(),runner_sha256=digest(Path(__file__)))
    rows=[];preview=[]
    if args.frames_run:
        frames=owner.cache('event-driven/'+args.frames_run)
        identity.update(observations_sha256=digest(frames/'observations.json'),preview_sha256=digest(frames/'video-only.json'))
        rows=read(frames/'observations.json')['observations'];preview=read(frames/'video-only.json')['teams']
    manifest=target/'manifest.json'
    if manifest.exists():
        old=read(manifest)
        if old['identity']!=identity:raise ValueError('Source changed; preserve namespace and choose another diagnostic ID')
        if old['status']=='complete':
            for name,h in old['outputs'].items():assert digest(target/name)==h
            assert digest(report)==old['report_sha256'];print('Completed saved-entry replay reused');return
    protected={}
    prior=owner.cache('evaluation/m238-provisional-entry-v2/preservation.json')
    if prior.exists():
        for check in read(prior)['checks']:
            assert digest(ROOT/check['path'])==check['expected']
            protected[check['path']]=check['expected']
    for name in ['replay.json','timeline.json','summary.json','manifest.json']:
        path=source.parent/name
        if path.exists():protected[str(path.relative_to(ROOT))]=digest(path)
    for diagnostic in ['m238-entry-hud-v3','m238-entry-hud-v4']:
        previous=owner.cache('evaluation/'+diagnostic)
        if previous!=target and previous.exists():
            for name in ['replay.json','timeline.json','summary.json','manifest.json','preservation.json','semantic-review.json','browser-v1/validation.json']:
                path=previous/name
                if path.exists():protected[str(path.relative_to(ROOT))]=digest(path)
    for path in owner.report('').rglob('*.md'):
        protected[str(path.relative_to(ROOT))]=digest(path)
    atomic_json(target/'preservation.json',dict(status='running',files=protected))
    atomic_json(manifest,dict(status='running',identity=identity))
    start=time.monotonic();cpu=time.process_time();original=read(source);engine=StateEngine(from_dict(original['initial_state']))
    engine.history=[EventRecord(deepcopy(h['event']),h['delivery_index'],deepcopy(h['ordering']),retracted=h.get('retracted',False)) for h in original['history']]
    timeline=[];violations=[];changed=[];regressions=[];by_id={h['event']['event_id']:h for h in original['history']}
    def capture(record,state):
        e=record.bindings.get('resolved_event',record.event);t=e['attributes']['observation_time']
        view=slots(state)
        for side,team in state.sides.items():
            if len(team.active_slots)!=len(set(team.active_slots.values())):violations.append(dict(event_id=e['event_id'],kind='duplicate_active_instance'))
            for pid in team.active_slots.values():
                p=state.pokemon[pid];ep=current_episode(state,pid)
                if any(ts>t for ts in source_times(p.species.provenance)):violations.append(dict(event_id=e['event_id'],kind='future_species_fact'))
                if ep and ep.get('species_resolution_time') is not None and ep['species_resolution_time']>t:violations.append(dict(event_id=e['event_id'],kind='future_resolution'))
        timeline.append(dict(timestamp=t,event_id=e['event_id'],type=e['event_type'],raw=e['original_text'],application_status=record.application_status,slots=view))
        old=by_id[e['event_id']]
        if (old['application_status'],old['reason'])!=(record.application_status,record.reason):
            change=dict(event_id=e['event_id'],timestamp=t,raw=e['original_text'],before=[old['application_status'],old['reason']],after=[record.application_status,record.reason]);changed.append(change)
            if old['application_status'].startswith('applied') and not record.application_status.startswith('applied'):regressions.append(change)
        if record.delivery_index%100==0:
            atomic_json(target/'progress.json',dict(completed=record.delivery_index,total=len(engine.history),timeline=timeline,violations=violations,changed=changed))
            print(owner.battle_id,record.delivery_index,'/',len(engine.history),flush=True)
    try:
        with ExitStack() as stack:
            for name in ['recognition.fast_video.CachedOCR.read','recognition.fast_video.CachedOCR.predict','recognition.fast_video.CachedIcons.identify',
                         'recognition.fast_video.decoded_frames','cv2.imread','cv2.VideoCapture']:
                stack.enter_context(patch(name,forbidden))
            engine.replay(snapshot_callback=capture)
        replay_seconds=time.monotonic()-start;probe_started=time.monotonic();probes=[]
        receipts=engine.state.knowledge.get('command_reconciliation',{}).get('receipts',[])
        summary=dict(battle_id=owner.battle_id,records=len(engine.history),recognition_calls=0,video_decoding=0,
            before=dict(Counter(h['application_status'] for h in original['history'])),after=dict(Counter(h.application_status for h in engine.history)),
            changes=changed,previously_applied_regressions=regressions,invariants=violations,
            command_outcomes=dict(Counter(o['status'] for r in receipts for o in r['outcomes'])),corrections=sum(r['corrections'] for r in receipts),
            entry_episodes=deepcopy(engine.state.knowledge.get('active_entry_episodes',[])),
            provisional_episodes=[ep for ep in engine.state.knowledge.get('active_entry_episodes',[]) if ep.get('display_reference')],
            model_probes=probes,replay_seconds=replay_seconds,probe_seconds=time.monotonic()-probe_started,
            wall_seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu,
            peak_process_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024))
        summary['final_slot_changes']={side:dict(before=original['state']['sides'][side]['active_slots'],after=team.active_slots)
            for side,team in engine.state.sides.items() if original['state']['sides'][side]['active_slots']!=team.active_slots}
        summary['hud_opportunities']=[dict(timestamp=r['timestamp'],phase=r['ui']['phase'],source_id=r['source_id'],sha256=r['sha256'],
            huds=[dict(slot=m['slot'],raw=(m.get('species') or {}).get('raw_text'),icon_status=(m.get('icon') or {}).get('status'),species_id=(m.get('icon') or {}).get('species_id'),reused=m.get('identity_reused_from'))
                for m in r.get('snapshot',{}).get('pokemon',[])]) for r in rows if r.get('snapshot',{}).get('pokemon')]
        summary['remaining_deferred']=[dict(timestamp=h.event['attributes'].get('observation_time'),text=h.event['original_text'],reason=h.reason) for h in engine.history if h.application_status=='deferred']
        for path,expected in protected.items():assert digest(ROOT/path)==expected,path
        atomic_json(target/'preservation.json',dict(status='passed',files=protected,checks=len(protected)))
        atomic_json(target/'replay.json',engine.to_dict());atomic_json(target/'timeline.json',timeline);atomic_json(target/'summary.json',summary)
        timeline_html(target,report,timeline,summary,rows)
        assert digest(source)==identity['baseline_sha256'];assert runtime_sources()==identity['sources']
        finish=dict(status='complete',identity=identity,outputs={name:digest(target/name) for name in ['replay.json','timeline.json','summary.json','preservation.json']},report_sha256=digest(report))
        atomic_json(manifest,finish)
        print(json.dumps({k:v for k,v in summary.items() if k not in ['model_probes','provisional_episodes','hud_opportunities','remaining_deferred','entry_episodes','changes','previously_applied_regressions']},ensure_ascii=False,indent=2),flush=True)
    except BaseException as exc:
        atomic_json(manifest,dict(status='failed',identity=identity,error=repr(exc)));raise


if __name__=='__main__':main()
