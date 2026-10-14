"""Offline M2.2.1 timeline export and browser-script regressions."""
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from scripts.replay_m22 import run
from tracking.state_timeline import build_timeline, field_diff, render_html, semantic_diff, pack_timeline, unpack_timeline

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def saved():
    return run(ROOT/'tests/fixtures/battles/sample_battle_2/reviewed_events.json', ROOT/'tests/fixtures/m22_initial_context.json')[0].to_dict()


@pytest.fixture(scope='module')
def snapshots():
    return run(ROOT/'tests/fixtures/battles/sample_battle_2/reviewed_events.json', ROOT/'tests/fixtures/m22_initial_context.json')[1]


@pytest.fixture(scope='module')
def timeline(saved, snapshots):
    return build_timeline(saved['history'], saved['initial_state'], snapshots, saved['state'])


def changes(entry, suffix, category=None):
    return [c for c in entry['changes'] if c['path'][-len(suffix):] == suffix
            and (category is None or c['category'] == category)]


def test_real_twenty_event_transition_oracle(timeline):
    entries = timeline['entries']
    assert [e['sequence'] for e in entries] == list(range(21))
    assert entries[0]['before'] is None and entries[0]['turn'] is None
    assert all(e['turn'] == 2 for e in entries[1:])
    for out, incoming, side, slot, before_name, after_name in [
        (1, 2, 'opponent', 'left', '雷丘', '爱管侍'),
        (5, 6, 'self', 'left', '轰擂金刚猩', '蚊香蛙皇'),
        (17, 18, 'opponent', 'right', '红莲铠骑', '大狃拉')]:
        removal = changes(entries[out], ['sides', side, 'active_slots', slot], 'gameplay')[0]
        insertion = changes(entries[incoming], ['sides', side, 'active_slots', slot], 'gameplay')[0]
        assert entries[out]['before']['pokemon'][removal['before']]['species']['value']['name'] == before_name
        assert removal['after'] == insertion['before'] == {'timeline_missing': True}
        assert entries[incoming]['after']['pokemon'][insertion['after']]['species']['value']['name'] == after_name
    weather = changes(entries[8], ['weather', 'kind'], 'gameplay')[0]
    assert weather['before']['value'] == 'snow' and weather['after']['value'] == 'rain'
    assert entries[4]['after']['terrain']['kind']['value'] == 'psychic'
    hp = changes(entries[10], ['hp', 'current'], 'gameplay')[0]
    assert (hp['before']['value'], hp['after']['value']) == (197, 173)
    assert changes(entries[17], ['fainted'], 'gameplay')[0]['after']['value'] is True
    assert changes(entries[19], ['item', 'activations'], 'knowledge')
    assert not any('stages' in c['path'] for c in entries[19]['changes'])
    stage = changes(entries[20], ['stages', 'special_defense', 'changes'], 'gameplay')[0]
    assert stage['before'] == [] and stage['after'][0]['amount'] is None
    pid = stage['path'][1]
    final_stage = entries[20]['after']['pokemon'][pid]['stages']['special_defense']
    assert final_stage['value']['knowledge'] == 'unknown'
    assert stage['after'][0]['prior_known_value'] is None
    for i in (11, 14):
        assert entries[i]['classification'] == 'observation_only'
        assert not any(c['category'] == 'gameplay' for c in entries[i]['changes'])
        assert entries[i]['raw_changes']  # Observation ledger really changes.
    for e in entries[1:]:
        assert e['event']['original_text'] and e['event']['evidence']
        assert e['event']['ocr_confidence'] is not None
        assert field_diff(e['before'], e['after']) == e['raw_changes']


def test_fresh_replay_matches_all_exported_snapshots(timeline):
    engine, replayed = run(ROOT/'tests/fixtures/battles/sample_battle_2/reviewed_events.json', ROOT/'tests/fixtures/m22_initial_context.json')
    # Historical M2.2 artifacts predate additive mechanic fields; compare every
    # original gameplay/knowledge field while M2.2.2 tests cover new snapshots.
    def original_fields(value):
        if isinstance(value,dict):
            return {k:original_fields(v) for k,v in value.items() if k not in {'mechanics','current_types'}}
        if isinstance(value,list): return [original_fields(v) for v in value]
        return value
    assert original_fields(timeline['entries'][-1]['after']) == original_fields(engine.state.to_dict())
    assert original_fields([e['after'] for e in timeline['entries'][1:]]) == original_fields([s['state'] for s in replayed])
    for before, after in zip(timeline['entries'], timeline['entries'][1:]):
        assert before['after'] == after['before']


def test_field_diff_and_knowledge_classification():
    a = {'value': False, 'knowledge': 'derived', 'provenance': [{'event_id': 'a'}], 'alternatives': []}
    b = deepcopy(a); b['knowledge'] = 'observed'; b['provenance'] = [{'event_id': 'b'}]
    diff = semantic_diff({'fainted': a}, {'fainted': b})
    assert len(diff) == 1 and diff[0]['category'] == 'knowledge'
    b['knowledge'] = 'derived'
    assert semantic_diff({'fainted': a}, {'fainted': b}) == []
    assert any(c['path'] == ['fainted', 'provenance'] for c in field_diff({'fainted': a}, {'fainted': b}))
    b['knowledge'] = 'conflicting'; b['alternatives'] = [{'value': True}]
    diff = semantic_diff({'fainted': a}, {'fainted': b})
    assert diff[0]['category'] == 'knowledge' and diff[0]['after']['alternatives']
    assert field_diff({'a': 1}, {'b': 2}) == [
        {'path': ['a'], 'before': 1, 'after': {'timeline_missing': True}},
        {'path': ['b'], 'before': {'timeline_missing': True}, 'after': 2}]
    assert semantic_diff({'changes': []}, {}) == []


def test_no_bookkeeping_in_gameplay(timeline):
    for entry in timeline['entries']:
        for change in entry['changes']:
            if change['category'] == 'gameplay':
                assert not set(change['path']) & {'provenance', 'event_id', 'initiated_by', 'last_tick',
                                                  'party_instance_ids', 'fainted_instance_ids', 'vacant_slots'}
    # An existing false faint fact is reaffirmed on send-out, not a new faint transition.
    assert not changes(timeline['entries'][6], ['fainted'], 'gameplay')
    # Creating an instance doesn't imply activation of every empty history list.
    assert not changes(timeline['entries'][2], ['item', 'activations'])


def test_deterministic_html_data_completeness_and_safe_embedding(timeline):
    html = render_html(timeline)
    assert html == render_html(deepcopy(timeline))
    embedded = re.search(r'<script type="application/json" id="timeline-data">(.*?)</script>', html, re.S).group(1)
    assert unpack_timeline(json.loads(embedded)) == timeline
    assert not re.search(r'<(?:script|link|img)[^>]+(?:src|href)=', html)
    poisoned = deepcopy(timeline)
    poisoned['entries'][1]['event']['original_text'] = '</script><script>alert(1)</script>&'
    safe = render_html(poisoned)
    embedded = re.search(r'<script type="application/json" id="timeline-data">(.*?)</script>', safe, re.S).group(1)
    assert '</script>' not in embedded
    assert unpack_timeline(json.loads(embedded)) == poisoned


@pytest.mark.parametrize('failure', ['duplicate', 'missing', 'state_hash', 'status', 'final', 'mixed_order'])
def test_reject_inconsistent_inputs(saved, snapshots, failure):
    history, snaps, final = deepcopy(saved['history']), deepcopy(snapshots), deepcopy(saved['state'])
    if failure == 'duplicate': snaps.append(deepcopy(snaps[0]))
    if failure == 'missing': snaps.pop()
    if failure == 'state_hash': snaps[0]['state_hash'] = 'wrong'
    if failure == 'status': snaps[0]['application_status'] = 'rejected'
    if failure == 'final': final['battle_id'] = 'wrong'
    if failure == 'mixed_order': history[0]['ordering']['domain'] = 'time'
    with pytest.raises(ValueError):
        build_timeline(history, saved['initial_state'], snaps, final)


def test_reusable_cli_with_another_battle_id(saved, snapshots, tmp_path):
    # All serialized state hashes must be updated together for this independent input.
    from tracking.state_timeline import state_hash
    payload, snaps = deepcopy(saved), deepcopy(snapshots)
    payload['initial_state']['battle_id'] = 'another-battle'
    payload['state']['battle_id'] = 'another-battle'
    for snapshot, record in zip(snaps, payload['history']):
        snapshot['state']['battle_id'] = 'another-battle'
        snapshot['state_hash'] = record['state_hash'] = state_hash(snapshot['state'])
    history_path, snapshots_path = tmp_path/'history.json', tmp_path/'snapshots.json'
    history_path.write_text(json.dumps(payload)); snapshots_path.write_text(json.dumps({'snapshots': snaps}))
    html_path, json_path = tmp_path/'viewer.html', tmp_path/'timeline.json'
    import sys
    subprocess.run([sys.executable, str(ROOT/'scripts/export_m221.py'), '--history', str(history_path),
                    '--snapshots', str(snapshots_path), '--output', str(html_path), '--json-output', str(json_path)],
                   check=True, capture_output=True)
    assert json.loads(json_path.read_text())['battle_id'] == 'another-battle'
    assert html_path.read_text() == render_html(json.loads(json_path.read_text()))


def test_javascript_all_states_navigation_and_filters(timeline, tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable for offline JavaScript smoke test')
    html = render_html(timeline)
    script = re.findall(r'<script>(.*?)</script>', html, re.S)[0]
    # A minimal DOM exercises rendering and handlers, without claiming browser/layout QA.
    harness = '''
const assert=require('node:assert/strict');
class Element {
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.value='all';this.attrs={};this._text='';}
 set textContent(v){this._text=String(v);this.children=[];} get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 append(...nodes){this.children.push(...nodes);} replaceChildren(...nodes){this.children=nodes;this._text='';}
 setAttribute(k,v){this.attrs[k]=v;}
}
const nodes={},listeners={};
global.document={getElementById:id=>nodes[id]??(nodes[id]=new Element()),createElement:tag=>new Element(tag),addEventListener:(key,fn)=>listeners[key]=fn};
'''
    harness += 'document.getElementById("timeline-data").textContent='+json.dumps(json.dumps(pack_timeline(timeline), ensure_ascii=False))+';\n'
    harness += script
    harness += '''
assert.equal(nodes.events.children.length,21);
for(let i=0;i<21;i++){
 nodes.events.children[i].onclick();
 assert.equal(nodes['after-json'].textContent,'');
 nodes['after-json'].loadJson();
 assert.equal(JSON.parse(nodes['after-json'].textContent).battle_id,timeline.battle_id);
 assert.deepEqual(JSON.parse(nodes['after-json'].textContent),entries[i].after);
 assert.equal(nodes.events.children[i].attrs['aria-current'],'true');
 assert(nodes.persistent.textContent.includes('戏法空间'));
 for(const filter of ['all','gameplay','knowledge','observation']){nodes.filter.value=filter;nodes.filter.onchange();}
}
nodes.events.children[0].onclick();assert(nodes.prev.disabled);nodes.next.onclick();assert.equal(selected,1);
listeners.keydown({target:{tagName:'BODY'},key:'ArrowRight',preventDefault(){}});assert.equal(selected,2);
listeners.keydown({target:{tagName:'BODY'},key:'ArrowLeft',preventDefault(){}});assert.equal(selected,1);
nodes.events.children[20].onclick();assert(nodes.next.disabled);
console.log('All 21 states, filters, buttons, and arrow keys rendered successfully.');
'''
    path = tmp_path/'viewer-smoke.cjs'; path.write_text(harness)
    result = subprocess.run([node, str(path)], check=True, capture_output=True, text=True)
    assert 'All 21 states' in result.stdout


def test_compact_transport_shares_snapshots_and_preserves_reserved_data(timeline):
    original=deepcopy(timeline)
    original['metadata']={'__proto__':{'polluted':True},'ref':['ref',12],'format':'interned-timeline-v1'}
    packed=pack_timeline(original)
    assert unpack_timeline(packed)==original
    restored=unpack_timeline(packed)
    assert restored['entries'][1]['after'] is restored['entries'][2]['before']
    assert len(json.dumps(packed)) < len(json.dumps(original)) / 2
    assert original['entries'][1]['after']==timeline['entries'][1]['after']
    assert pack_timeline(original)==pack_timeline(deepcopy(original))


def test_lazy_debug_panels_refresh_when_open(timeline, tmp_path):
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable')
    path=tmp_path/'compact.html';path.write_text(render_html(timeline))
    result=subprocess.run([node,str(ROOT/'scripts/benchmark_state_timeline.cjs'),str(path)],
                          check=True,capture_output=True,text=True)
    metrics=json.loads(result.stdout)
    assert metrics['smoke_passed'] and metrics['states']==len(timeline['entries'])
