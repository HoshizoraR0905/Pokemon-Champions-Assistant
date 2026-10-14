"""Concrete cached HUD assertions; never decode frames, run OCR, or write reports."""
import json
from pathlib import Path
import pytest
from tracking.state_engine import StateEngine

ROOT=Path(__file__).resolve().parents[1]
REQUIRED=tuple(f'reports/battles/sample_battle_{n}/M2.3.3-A-state.json' for n in range(5))
pytestmark=pytest.mark.local_artifacts(*REQUIRED)


@pytest.fixture(scope='module')
def hud_prefixes():
    result={}
    for n in range(5):
        envelope=json.loads((ROOT/REQUIRED[n]).read_text())
        assert not envelope['initial_state']['pokemon']
        engine=StateEngine.from_dict(envelope);rows=[]
        def capture(record,state):
            e=record.event
            if e['event_type']=='hud_observation' and record.bindings.get('actor'):
                p=state.pokemon[record.bindings['actor']['pokemon_instance_id']]
                rows.append(dict(time=e['attributes']['observation_time'],slot=e['attributes']['slot'],side=e['side'],
                    species=p.species.value['species_id'],pid=p.pokemon_instance_id,hp=p.hp.current.value,
                    maximum=p.hp.maximum.value,receipt=record.bindings['hud']))
        engine.replay(snapshot_callback=capture);result[n]=rows
    return result


def test_corviknight_and_unknown_transition(hud_prefixes):
    row=next(r for r in hud_prefixes[0] if r['side']=='self' and r['slot']=='right' and abs(r['time']-364.011667)<.001)
    assert row['species']==823 and (row['hp'],row['maximum'])==(162,173)
    interval=row['receipt']['occupancy_change']
    assert interval['at_or_before']==row['time'] and interval['cause'] is None and interval['action_time'] is None


def test_armarouge_hp_updates_without_damage_inference(hud_prefixes):
    rows=[r for r in hud_prefixes[4] if r['side']=='self' and r['slot']=='right' and r['species']==936]
    assert (rows[0]['hp'],rows[0]['maximum'])==(117,162)
    assert abs(rows[0]['time']-432.073333)<.001
    assert (rows[1]['hp'],rows[1]['maximum'])==(66,162)
    assert rows[0]['pid']==rows[1]['pid']


def test_salamence_hp_instance_continuity(hud_prefixes):
    rows=[r for r in hud_prefixes[1] if r['side']=='self' and r['slot']=='left' and r['species']==373]
    values=[]
    for r in rows:
        if not values or values[-1]!=r['hp']:values.append(r['hp'])
    assert values==[172,106,52]
    assert len({r['pid'] for r in rows})==1
    assert all(r['maximum']==172 for r in rows)


def test_early_froslass_and_rillaboom_are_present(hud_prefixes):
    rows=[r for r in hud_prefixes[2] if r['side']=='self' and r['slot']=='left']
    assert rows[0]['species']==478 and rows[0]['time']<141
    assert any(r['species']==812 and r['time']<267 for r in rows)
    assert any(r['species']==186 and r['time']>344 for r in rows)
