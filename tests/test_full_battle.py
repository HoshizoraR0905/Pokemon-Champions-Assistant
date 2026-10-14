"""M2.2.3 multi-turn integration, plus the saved human-assisted real replay."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from battle_events import EventParser, BattleContext
from recognition.battle_log import assemble_views, detect_log
from tracking.battle_state import BattleState, PokemonState, Fact, fact, from_dict
from tracking.state_engine import StateEngine, hash_state
from tracking.state_timeline import build_timeline, render_html, state_hash
from tracking.mechanics import read

ROOT=Path(__file__).resolve().parents[1]


def event(n,kind,attrs=None,*,turn=1,actor=None,side='self',refs=None):
    return {'event_id':f'integration:{n}','event_type':kind,'side':side,'actor':actor,'target':None,
            'original_text':kind,'canonical_references':refs or {},'log_order':None,
            'evidence':[{'source_type':'synthetic','source_id':'multi-turn-software-test','observation_ids':[str(n)],
                         'details':{'turn':turn} if turn is not None else {}}],
            'ocr_confidence':None,'parsing_confidence':'supported','uncertainty':[],
            'attributes':dict(attrs or {},sequence=n),'status':'confirmed','associated_video_evidence':[]}


def base():
    state=BattleState('integration');p=PokemonState('stable:member','self')
    p.species=fact(EventParser().identity('雪妖女','species'),{'source':'synthetic'})
    p.original_identity=deepcopy(p.species);p.location=fact({'kind':'active','slot':'left'},{'source':'synthetic'})
    p.hp.current=fact(150,{'source':'synthetic'});p.hp.maximum=fact(177,{'source':'synthetic'})
    p.major_status=fact('burn',{'source':'synthetic'})
    state.pokemon[p.pokemon_instance_id]=p;state.sides['self'].party_instance_ids=[p.pokemon_instance_id]
    state.sides['self'].active_slots={'left':p.pokemon_instance_id}
    return StateEngine(state)


def apply(engine,n,kind,attrs=None,**kwargs):
    attrs=dict(attrs or {})
    if kwargs.get('side','self')!='field':attrs.setdefault('actor_instance_id','stable:member')
    return engine.apply(event(n,kind,attrs,**kwargs))


def test_multi_turn_switch_preserves_hp_status_and_changes_entry():
    engine=base();old=read(engine.state.pokemon['stable:member'].mechanics['field_entry'],'entry_id').value
    apply(engine,1,'turn_boundary',{'turn':1,'boundary':'end'},side='field')
    apply(engine,2,'turn_boundary',{'turn':2,'boundary':'start'},turn=2,side='field')
    apply(engine,3,'switch_out',turn=2)
    apply(engine,4,'send_out',{'slot':'left'},turn=3)
    p=engine.state.pokemon['stable:member']
    assert p.hp.current.value==150 and p.major_status.value=='burn'
    assert read(p.mechanics['field_entry'],'entry_id').value!=old
    assert list(engine.state.pokemon)==['stable:member']
    serialized=engine.to_dict();assert StateEngine.from_dict(serialized).to_dict()==serialized


def test_menu_reveals_move_without_executing_it():
    engine=base();ref=EventParser().identity('守住','move')
    result=apply(engine,1,'move_observation',{'move_slot':1,'pp':{'current':8,'maximum':8}},refs={'move':ref})
    assert result.application_status=='applied_confirmed'
    p=engine.state.pokemon['stable:member']
    assert p.moves.known_slots['1'].value==ref and not p.moves.executed
    assert 'protect_chain' not in p.mechanics
    assert apply(engine,2,'move_observation',{'move_slot':1,'pp':{'current':9,'maximum':8}},refs={'move':ref}).application_status=='rejected'
    assert engine.state.pokemon['stable:member'].moves.pp[ref['canonical_id']].value['current']==8


def test_replay_snapshot_callback_matches_incremental_prefixes():
    engine=base();expected=[]
    for n,kind,attrs in [(1,'stat_change',{'stats':['attack'],'change':'replace','value':1}),
                         (2,'switch_out',{'invalidate_unverified_persistence':True}),
                         (3,'send_out',{'slot':'left'}),
                         (4,'move_effect',{'effect':'observation'})]:
        apply(engine,n,kind,attrs)
        expected.append((engine.history[-1].event['event_id'],hash_state(engine.state),engine.state.to_dict()))
    actual=[]
    engine.replay(snapshot_callback=lambda record,state:actual.append((record.event['event_id'],record.state_hash,state.to_dict())))
    assert actual==expected


def test_observed_effect_duration_does_not_restart_or_double_tick():
    engine=base()
    apply(engine,1,'weather_change',{'weather':'rain','change':'start'},side='field')
    initiated=deepcopy(engine.state.weather.initiated_by)
    apply(engine,2,'weather_change',{'weather':'rain','change':'observe','duration':{'remaining':2,'timing':'turn_end'}},side='field')
    assert engine.state.weather.initiated_by==initiated
    apply(engine,3,'turn_boundary',{'turn':1,'boundary':'end'},side='field')
    assert engine.state.weather.duration.remaining.value==1
    apply(engine,4,'turn_boundary',{'turn':2,'boundary':'start'},side='field',turn=2)
    assert engine.state.weather.duration.remaining.value==1
    apply(engine,5,'turn_boundary',{'turn':2,'boundary':'end'},side='field',turn=2)
    assert engine.state.weather.active.value is False


def test_history_gap_invalidates_duration_and_missing_turn_stays_explicit():
    engine=base()
    apply(engine,1,'terrain_change',{'terrain':'grassy','change':'start','duration':{'remaining':3,'timing':'turn_end'}},side='field')
    apply(engine,2,'turn_boundary',{'turn':4,'boundary':'start'},turn=4,side='field')
    assert not engine.state.terrain.duration.remaining.known
    e=event(3,'move_effect',{'effect':'unattributed observation'},turn=None,side='field')
    e['attributes'].pop('sequence')
    assert engine.apply(e).application_status=='deferred'
    assert engine.history[-1].reason=='missing_or_ambiguous_event_order'


def test_explicit_unknown_switch_persistence_and_faint_hp():
    engine=base()
    apply(engine,1,'stat_change',{'stats':['attack'],'change':'replace','value':2})
    apply(engine,2,'switch_out',{'invalidate_unverified_persistence':True})
    p=engine.state.pokemon['stable:member']
    assert not p.stages['attack'].value.known and p.hp.current.value==150
    apply(engine,3,'send_out',{'slot':'left'})
    apply(engine,4,'faint')
    assert engine.state.pokemon['stable:member'].fainted.value is True
    assert not engine.state.pokemon['stable:member'].hp.current.known


def test_mega_awaits_new_ability_and_preserves_entry_and_identity():
    engine=base();p=engine.state.pokemon['stable:member']
    p.ability.current=fact(EventParser().identity('咒术之躯','ability'),{'source':'synthetic'})
    # Seed the initial context, not only the replay-derived current object.
    engine.initial.pokemon['stable:member'].ability=deepcopy(p.ability)
    old=read(p.mechanics['field_entry'],'entry_id').value
    apply(engine,1,'transformation',{'mechanic':'mega_evolution','identity':EventParser().identity('超级雪妖女','species')})
    p=engine.state.pokemon['stable:member'];assert not p.ability.current.known
    assert read(p.mechanics['field_entry'],'entry_id').value==old
    assert p.original_identity.value['species_id']==478 and p.hp.current.value==150
    apply(engine,2,'ability_activation',refs={'ability':EventParser().identity('降雪','ability')})
    assert engine.state.pokemon['stable:member'].ability.current.value['canonical_id']=='pokeapi:ability:117'
    assert read(engine.state.pokemon['stable:member'].mechanics['entry_triggers'],'activation_count').value==1


def test_alias_requires_evidence_and_keeps_original_text():
    parser=EventParser();context=BattleContext()
    row={'entry_id':'alias','raw_text':'对手的Sally使出了守住！','turn':1,'log_order':1,'source_id':'test',
         'ocr_confidence':.99,'color':None,'observation_ids':['test']}
    assert parser.parse(row,context).actor is None
    context.display_aliases['Sally']={'identity':parser.identity('暴飞龙','species'),'evidence':[{'image':'observed-icon.png'}]}
    parsed=parser.parse(row,context)
    assert parsed.actor['species_id']==373 and parsed.original_text==row['raw_text']
    assert parsed.attributes['display_alias_evidence']


def test_overlap_reopening_and_identical_text_on_distinct_turns():
    def view(turn,ts,top,texts):
        return {'turn':turn,'timestamp':ts,'source_id':f'video#{ts}','detected':True,'geometry':{'scroll_top':top},
            'observations':[{'raw_text':t,'observation_id':f'{ts}:{i}','source_id':f'video#{ts}','ocr_confidence':.99,
                             'partial':False,'color':None} for i,t in enumerate(texts)]}
    views=[view(1,1,0,['甲','守住','成功']),view(1,2,1,['守住','成功','乙']),
           view(1,3,0,['甲','守住','成功']),view(2,4,0,['甲','守住','成功'])]
    entries,issues=assemble_views(views,ignore_partial_overlap=True)
    assert not issues
    assert [e['raw_text'] for e in entries if e['turn']==1]==['甲','守住','成功','乙']
    assert len(entries)==7 and len({e['entry_id'] for e in entries})==7


@pytest.mark.local_artifacts('reports/M2.2.3-evidence/m223-survey-000149.jpg')
def test_dim_scene_dividers_segment_six_rows():
    import cv2
    path=ROOT/'reports/M2.2.3-evidence/m223-survey-000149.jpg'
    # This surveyed screenshot is retained separately from model execution.
    if not path.exists():path=ROOT/'.cache/m223-survey/000149.jpg'
    geometry=detect_log(cv2.imread(str(path)))
    assert geometry is not None and len(geometry['separators'])==5


@pytest.fixture(scope='module')
def saved():
    return json.loads((ROOT/'reports/M2.2.3-battle-state.json').read_text())


@pytest.mark.local_artifacts('reports/M2.2.3-battle-state.json')
def test_saved_real_replay_determinism_dedup_and_final_state(saved):
    engine=StateEngine.from_dict(saved)
    assert json.loads(json.dumps(engine.to_dict()))==saved
    for record in saved['history']:engine.apply(record['event'])
    assert json.loads(json.dumps(engine.to_dict()))==saved
    assert not engine.state.conflicts
    assert engine.state.phase.value=='battle_end' and engine.state.turn.value==8
    assert engine.mechanic_rules.profile_id=='champions-evidence-only-v1'
    own={p.species.value['species_id']:p for p in engine.state.pokemon.values() if p.side_id=='self'}
    assert (own[478].hp.current.value,own[1018].hp.current.value)==(47,75)
    assert own[478].pokemon_instance_id in engine.initial.pokemon
    assert read(own[478].mechanics['field_entry'],'entry_id').value!=read(engine.initial.pokemon[own[478].pokemon_instance_id].mechanics['field_entry'],'entry_id').value
    opponent=[p for p in engine.state.pokemon.values() if p.side_id=='opponent']
    assert {p.species.value['species_id'] for p in opponent if p.fainted.value is True}=={812,903}
    assert all(not p.hp.current.known and not p.hp.maximum.known for p in opponent)
    assert engine.state.sides['opponent'].remaining_available.value==2
    assert all('unburden' not in p.mechanics for p in opponent)


@pytest.mark.local_artifacts('reports/M2.2.3-state-snapshots.json')
def test_real_prefix_continuity_and_snapshot_hashes(saved):
    snapshots=json.loads((ROOT/'reports/M2.2.3-state-snapshots.json').read_text())['snapshots']
    assert len(snapshots)==len(saved['history'])
    assert [s['event_id'] for s in snapshots]==[r['event']['event_id'] for r in saved['history']]
    assert snapshots[-1]['state']==saved['state']
    boundaries=[]
    def gameplay(value):
        if isinstance(value,dict):return {k:gameplay(v) for k,v in value.items() if k!='provenance'}
        if isinstance(value,list):return [gameplay(v) for v in value]
        return value
    for i,(snapshot,record) in enumerate(zip(snapshots,saved['history'])):
        assert state_hash(snapshot['state'])==snapshot['state_hash']==record['state_hash']
        e=record['event']
        if e['event_type']=='turn_boundary' and e['attributes']['boundary']=='start' and i:
            before=deepcopy(snapshots[i-1]['state']);after=deepcopy(snapshot['state'])
            # A heading must not alter party members or HP/status/entry identity.
            assert gameplay(before['sides'])==gameplay(after['sides'])
            assert gameplay(before['pokemon'])==gameplay(after['pokemon'])
            boundaries.append(e['attributes']['turn'])
    assert boundaries==list(range(2,9))


@pytest.mark.local_artifacts('reports/M2.2.3-full-battle-timeline.html')
def test_full_html_contains_every_event_and_turn_controls(saved):
    html=(ROOT/'reports/M2.2.3-full-battle-timeline.html').read_text()
    match=re.search(r'<script type="application/json" id="timeline-data">(.*?)</script>',html,re.S)
    from tracking.state_timeline import unpack_timeline
    timeline=unpack_timeline(json.loads(match[1]));assert len(timeline['entries'])==len(saved['history'])+1
    assert timeline['entries'][0]['after']==saved['initial_state']
    assert timeline['entries'][-1]['after']==saved['state']
    assert {e['turn'] for e in timeline['entries']}==set(range(1,9))
    assert 'turn-selector' in html and '证据截图' in html
    assert all(a['after']==b['before'] for a,b in zip(timeline['entries'],timeline['entries'][1:]))


@pytest.mark.local_artifacts('reports/M2.2.3-battle-state.json')
def test_independent_hp_and_identity_checkpoints(saved):
    results=json.loads((ROOT/'reports/M2.2.3-cross-source-validation.json').read_text())
    assert len(results['hp_checks'])==len(results['identity_checks'])==28
    assert all(v['result']=='match' for v in results['hp_checks']+results['identity_checks'])
    used={e['evidence'][0]['details']['original_cached_image'] for r in saved['history']
          if (e:=r['event'])['attributes'].get('observation_kind')=='settled_display'}
    assert len(used)==2
    assert not used.intersection(v['image'] for v in results['hp_checks'])


def test_turn_selector_and_first_last_navigation_in_node(tmp_path):
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable')
    # Eight real initial-context field layouts, compact synthetic boundaries.
    initial=json.loads((ROOT/'tests/fixtures/m223_initial_context.json').read_text())['state']
    engine=StateEngine(from_dict(initial));snapshots=[]
    for turn in range(1,9):
        e=event(turn,'turn_boundary',{'turn':turn,'boundary':'start'},turn=turn,side='field')
        r=engine.apply(e);snapshots.append({'event_id':e['event_id'],'application_status':r.application_status,
                                          'state_hash':hash_state(engine.state),'state':engine.state.to_dict()})
    timeline=build_timeline(engine.to_dict()['history'],engine.initial.to_dict(),snapshots,engine.state.to_dict())
    script=re.findall(r'<script>(.*?)</script>',render_html(timeline),re.S)[0]
    harness='''const assert=require('assert');
class Element {constructor(tag='DIV'){this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this.value='all';this._text='';}
set textContent(v){this._text=String(v);this.children=[];} get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
append(...nodes){this.children.push(...nodes);} replaceChildren(...nodes){this.children=[...nodes];this._text='';} setAttribute(k,v){this.attrs[k]=v;}}
const nodes={},listeners={};global.document={getElementById:id=>nodes[id]??(nodes[id]=new Element()),createElement:t=>new Element(t),addEventListener:(k,fn)=>listeners[k]=fn};
'''
    harness+='document.getElementById("timeline-data").textContent='+json.dumps(json.dumps(timeline,ensure_ascii=False))+';\n'+script
    harness+='''
assert.equal(nodes['turn-selector'].children.length,8);
for(let turn=1;turn<=8;turn++){nodes['turn-selector'].value=String(turn);nodes['turn-selector'].onchange();assert.equal(entries[selected].turn,turn);}
nodes.events.children[0].onclick();assert(nodes.prev.disabled);nodes.next.onclick();assert.equal(selected,1);
nodes.events.children.at(-1).onclick();assert(nodes.next.disabled);
listeners.keydown({target:{tagName:'BODY'},key:'ArrowLeft',preventDefault(){}});assert.equal(selected,entries.length-2);
console.log('Multi-turn navigation passed');'''
    path=tmp_path/'multi-turn.cjs';path.write_text(harness)
    assert 'Multi-turn navigation passed' in subprocess.run([node,str(path)],check=True,capture_output=True,text=True).stdout
