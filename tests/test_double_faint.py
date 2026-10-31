"""The pair must be verified together from later, independent slot evidence."""
from copy import deepcopy
import pytest
from tests.test_identity_modes import mode_engine
from tests.test_switch_continuity import apply_text
from tests.test_evidence_fusion import hud, species
from tracking.double_faint import POLICY, pending_pair


def scenario(first_departure='对手的钢铠鸦倒下了！'):
    e = mode_engine()
    apply_text(e, 1, 'Guest派出了钢铠鸦！', slot='left')
    apply_text(e, 2, 'Guest派出了龙头地鼠！', slot='right')
    apply_text(e, 3, first_departure)
    apply_text(e, 4, '对手的龙头地鼠倒下了！')
    apply_text(e, 5, 'Guest派出了大狃拉！')  # Arrival order deliberately opposes HUD order.
    apply_text(e, 6, 'Guest派出了暴飞龙！')
    return e


def confirmation(t=7):
    h = hud(100,t,373,side='opponent',slot='left',hp=100)
    h.attributes['double_faint_hud'] = dict(policy=POLICY,timestamp=t,source_id=h.evidence[0].source_id,
        slots={slot:dict(species=species(sid),icon={},independent=True)
               for slot,sid in [('left',373),('right',903)]})
    return h


def test_unique_pair_preserves_instances_forms_and_prospective_history():
    e = scenario();pair = pending_pair(e.state,'opponent');assert pair
    ids = {ep['species_id']:ep['instance_id'] for ep in pair}
    identities = {pid:deepcopy(e.state.pokemon[pid].species) for pid in ids.values()}
    before = deepcopy(e.to_dict()['history'])
    r=e.apply(confirmation(),sequence=len(e.history)+1)
    assert not r.reason
    assert e.state.sides['opponent'].active_slots == dict(left=ids[373],right=ids[903])
    assert e.to_dict()['history'][:-1] == before
    assert all(e.state.pokemon[pid].species == identities[pid] for pid in ids.values())
    assert all(ep['placements'][0]['timestamp']==7 for ep in e.state.knowledge['active_entry_episodes'][-2:])
    r=e.apply(hud(101,8,903,side='opponent',slot='right',hp=72),sequence=len(e.history)+1)
    assert r.bindings['actor']['pokemon_instance_id']==ids[903]
    assert e.state.pokemon[ids[903]].hp.displayed_percent.value==72
    e.retract('hud:100',reason='invalid visual proof')
    assert e.state.sides['opponent'].active_slots=={}


@pytest.mark.parametrize('case', ['incomplete','ambiguous','conflicting','conditioned','wrong_time','wrong_source','form_conflict'])
def test_pair_abstains_atomically(case):
    e=scenario();h=confirmation();proof=h.attributes['double_faint_hud']
    if case=='incomplete':proof['slots'].pop('right')
    elif case=='ambiguous':proof['slots']['right']['species']=species(373)
    elif case=='conflicting':proof['slots']['right']['icon']=dict(status='resolved',species_id=530)
    elif case=='conditioned':proof['slots']['left']['independent']=False
    elif case=='wrong_time':proof['timestamp']=6
    elif case=='wrong_source':proof['source_id']='other battle'
    elif case=='form_conflict':proof['slots']['right']['species']['resolution']['canonical_identity']='pokeapi:pokemon:wrong'
    r=e.apply(h,sequence=len(e.history)+1)
    assert r.reason=='message_episode_occupancy_unresolved'
    assert e.state.sides['opponent'].active_slots=={}


def test_two_vacancies_from_withdrawal_do_not_qualify():
    e=scenario('Guest换下了钢铠鸦！')
    assert pending_pair(e.state,'opponent') is None
    r=e.apply(confirmation(),sequence=len(e.history)+1)
    assert r.reason=='message_episode_occupancy_unresolved'
    assert e.state.sides['opponent'].active_slots=={}
