from dataclasses import replace
import json
from pathlib import Path

import pytest

from capture import load_image
from models import EntityResolution, Observation, Pokemon, Recognition
from recognition import Recognizer
from recognition.paddle_ocr import model_path, create_ocr
from team_configuration import TeamConfiguration, REQUIRED, STATS
from knowledge import KnowledgeBase


FIXTURES = Path(__file__).parent / 'fixtures'
TEST_KB = KnowledgeBase()


def observed(value, canonical_id=None):
    mapped=TEST_KB.identities.for_key(canonical_id) if canonical_id and (
        canonical_id.startswith('pokeapi:species:') or canonical_id.startswith('pokeapi:form:')) else None
    resolution = (EntityResolution(canonical_id=canonical_id,status='resolved',method='exact',
        species_id=mapped['species_id'] if mapped else None,
        pokemon_id=mapped['pokemon_id'] if mapped else None,
        form_id=mapped['form_id'] if mapped else None,
        canonical_identity=mapped['canonical_identity'] if mapped else None,
        identity_status=mapped['identity_status'] if mapped else 'unresolved') if canonical_id else None)
    return Observation(value,.9,raw_text=str(value),resolution=resolution)


def result(slot, species_id, fields, index=0):
    return Recognition('synthetic',index,index,screen='team_configuration',
        components=['team_configuration','configuration_moves'],
        pokemon=[Pokemon(slot,observed('sample',f'pokeapi:species:{species_id}'),
                         configuration=fields)])


def test_merge_by_slot_not_species_and_keep_conflicts(tmp_path):
    team = TeamConfiguration()
    a = result('own_team_1',373,{'ability':observed('Intimidate','pokeapi:ability:22')})
    b = result('own_team_2',373,{'ability':observed('Moxie','pokeapi:ability:153')},1)
    c = result('own_team_1',373,{'ability':observed('Moxie','pokeapi:ability:153')},2)
    assert team.ingest(a)
    assert team.ingest(b)
    assert team.ingest(c)
    one,two = team.data['members'][:2]
    assert one['fields']['ability']['canonical_id']=='pokeapi:ability:22'
    assert one['fields']['ability']['status']=='conflicting'
    assert two['fields']['ability']['canonical_id']=='pokeapi:ability:153'
    assert one['instance_id'] != two['instance_id']
    assert not team.data['complete']
    path = tmp_path/'team.json'
    team.save(path)
    assert TeamConfiguration.load(path).data['conflicts']['own_team_1']==['ability']


def test_species_slot_conflict_does_not_attach_other_configuration():
    team = TeamConfiguration()
    team.ingest(result('own_team_1',373,{'hp':observed(172)},0))
    team.ingest(result('own_team_1',248,{'hp':observed(177)},1))
    field = team.data['members'][0]['fields']
    assert field['hp']['value']==172
    assert field['species']['status']=='conflicting'
    assert field['species']['conflicts'][0]['canonical_id']=='pokeapi:species:248'


def test_form_conflict_does_not_attach_other_configuration():
    team=TeamConfiguration()
    male=Recognition('synthetic',0,0,screen='team_configuration',
        pokemon=[Pokemon('own_team_1',observed('Indeedee','pokeapi:form:876'),
                         configuration={'hp':observed(137)})])
    female=Recognition('synthetic',1,1,screen='team_configuration',
        pokemon=[Pokemon('own_team_1',observed('Indeedee','pokeapi:form:10355'),
                         configuration={'hp':observed(155)})])
    team.ingest(male);team.ingest(female)
    fields=team.data['members'][0]['fields']
    assert fields['identity']['canonical_id']=='pokeapi:pokemon:876'
    assert fields['identity']['status']=='conflicting'
    assert fields['hp']['value']==137


def test_manual_correction_requires_known_id_and_preserves_old_evidence():
    team = TeamConfiguration()
    team.ingest(result('own_team_1',373,{'hp':observed(172)},0))
    with pytest.raises(ValueError):
        team.correct('own_team_1','ability',canonical_id='bogus',reviewer='trainer')
    team.correct('own_team_1','hp',value=173,reviewer='trainer',note='checked screenshot')
    field=team.data['members'][0]['fields']['hp']
    assert field['value']==173 and field['status']=='manual_verified'
    assert field['conflicts'][0]['value']==172
    team.ingest(result('own_team_1',373,{'hp':observed(172)},1))
    assert field['value']==173 and field['status']=='manual_verified'
    assert 'hp' in team.data['conflicts']['own_team_1']


@pytest.mark.skipif(not model_path('paddle-v6').exists(),reason='PaddleOCR model not installed')
def test_supplied_pages_field_by_field(tmp_path):
    truth=json.loads((FIXTURES/'m12_ground_truth.json').read_text())
    recognizer=Recognizer(create_ocr('paddle-v6'),icons=True)
    team=TeamConfiguration()
    for filename in ('team_configuration_moves.png','team_configuration_stats.png'):
        recognition=recognizer.recognize(load_image(FIXTURES/filename))
        assert team.ingest(recognition)
        regions={r['region']:r for r in truth['regions'] if r['image']==filename}
        for pokemon in recognition.pokemon:
            index=int(pokemon.slot.rsplit('_',1)[1])-1
            row,col=divmod(index,2)
            assert pokemon.species.raw_text==regions[f'config_name_{row}_{col}']['expected']
            identity=pokemon.species.resolution
            if identity.canonical_identity:
                mapped=TEST_KB.identities.for_key(identity.canonical_identity)
                assert identity.species_id==mapped['species_id']
                assert identity.pokemon_id==mapped['pokemon_id']
                assert identity.form_id==mapped['form_id']
            if pokemon.icon and pokemon.icon.status=='resolved':
                assert pokemon.icon.canonical_identity==TEST_KB.identities.for_key(
                    pokemon.icon.canonical_identity)['canonical_identity']
            assert pokemon.configuration['gender'].value==[
                'female','female','male','male','male','female'][index]
            if filename.endswith('moves.png'):
                for name,region in [('ability',f'ability_{row}_{col}'),
                                    ('held_item',f'item_{row}_{col}')]:
                    assert pokemon.configuration[name].raw_text==regions[region]['expected']
                    assert pokemon.configuration[name].resolution.method=='exact'
                for i in range(4):
                    obs=pokemon.configuration[f'move_{i+1}']
                    assert obs.raw_text==regions[f'config_move_{row}_{col}_{i}']['expected']
                    assert obs.resolution.method=='exact'
            else:
                for stat in STATS:
                    obs=pokemon.configuration[stat]
                    assert obs.value==int(regions[f'config_{row}_{col}_{stat}']['expected'])
    assert [m['names']['en'] for m in team.data['members']]==[
        'Salamence','Tyranitar','Corviknight','Excadrill','Indeedee','Sneasler']
    assert [m['species_id'] for m in team.data['members']]==[373,248,823,530,876,903]
    assert all(m['fields']['level']['value'] is None for m in team.data['members'])
    assert all(m['fields']['evs']['value'] is None for m in team.data['members'])
    assert all(m['fields']['nature']['value'] is None for m in team.data['members'])
    assert team.data['members'][4]['pokemon_id']==876
    assert team.data['members'][4]['canonical_identity']=='pokeapi:pokemon:876'
    assert team.data['members'][4]['form_id'] is None
    assert team.data['members'][2]['identity_status']=='resolved_unique'
    assert team.data['members'][2]['canonical_identity']=='pokeapi:pokemon:823'
    assert not team.data['complete']
    assert all(m['missing_fields'] for m in team.data['members'])
    path=tmp_path/'team.json'; team.save(path)
    assert TeamConfiguration.load(path).data['sources'][0]['sha256']==truth['images']['team_configuration_moves.png']['sha256']


def test_ambiguous_resolution_is_not_accepted():
    team=TeamConfiguration()
    ambiguous=Observation(None,.82,raw_text='???',resolution=EntityResolution(
        status='unresolved',method='ambiguous_fuzzy'))
    team.ingest(result('own_team_1',373,{'ability':ambiguous}))
    field=team.data['members'][0]['fields']['ability']
    assert field['value'] is None and field['canonical_id'] is None
    assert 'ability' in team.data['missing_fields']['own_team_1']


def test_complete_only_after_six_members_manual_review():
    team=TeamConfiguration()
    for slot in range(1,7):
        instance=f'own_team_{slot}'
        team.correct(instance,'species',canonical_id='pokeapi:species:373',reviewer='trainer')
        team.correct(instance,'identity',canonical_id='pokeapi:pokemon:373',reviewer='trainer')
        team.correct(instance,'ability',canonical_id='pokeapi:ability:22',reviewer='trainer')
        team.correct(instance,'held_item',canonical_id='pokeapi:item:1',reviewer='trainer')
        for move in ('move_1','move_2','move_3','move_4'):
            team.correct(instance,move,canonical_id='pokeapi:move:1',reviewer='trainer')
        for stat in STATS:
            team.correct(instance,stat,value=100,reviewer='trainer')
        if slot<6:
            assert not team.data['complete']
    assert team.data['complete']
    assert team.data['members'][0]['form_id'] is None
    assert team.data['members'][0]['fields']['identity']['status']=='manual_verified'


def test_v1_team_snapshot_migrates_without_defaulting_unresolved_variant():
    old=TeamConfiguration().data
    old['schema_version']=1
    for member in old['members']:
        member['fields'].pop('identity')
    old['members'][0]['fields']['species'].update(
        value='爱管侍',canonical_id='pokeapi:species:876',status='knowledge_resolved')
    old['members'][0]['species_id']=876
    migrated=TeamConfiguration(data=old)
    member=migrated.data['members'][0]
    assert migrated.data['schema_version']==2
    assert member['identity_status']=='species_only'
    assert member['pokemon_id'] is None
    assert not migrated.data['complete']


def test_v1_verified_form_migrates_to_pokemon_identity_with_history():
    old=TeamConfiguration().data
    old['schema_version']=1
    member=old['members'][0]
    member['fields'].pop('identity')
    member['fields']['species'].update(value='爱管侍',canonical_id='pokeapi:species:876',
                                        status='knowledge_resolved')
    member['species_id']=876
    member['fields']['form'].update(value=876,canonical_id='pokeapi:form:876',
                                   status='manual_verified',observations=[{'source_id':0}])
    migrated=TeamConfiguration(data=old).data['members'][0]
    assert migrated['canonical_identity']=='pokeapi:pokemon:876'
    assert migrated['pokemon_id']==876 and migrated['form_id'] is None
    assert migrated['fields']['form']['value'] is None
    assert migrated['fields']['identity']['status']=='manual_verified'
    assert migrated['legacy_form']['observations']==[{'source_id':0}]


def test_existing_v2_species_only_backfill_preserves_evidence_and_verification():
    old=json.loads((Path(__file__).parents[1]/'data/teams/my_team.json').read_text())
    member=old['members'][2]
    species_evidence=json.loads(json.dumps(member['fields']['species']['observations']))
    sources=json.loads(json.dumps(old['sources']))
    member['fields']['identity']={
        'value':None,'canonical_id':None,'status':'unknown','confidence':0.0,
        'observations':[],'conflicts':[]}
    member['fields']['hp']['status']='manual_verified'
    migrated=TeamConfiguration(data=old)
    fixed=migrated.data['members'][2]
    assert fixed['canonical_identity']=='pokeapi:pokemon:823'
    assert fixed['pokemon_id']==823 and fixed['form_id'] is None
    assert fixed['fields']['identity']['status']=='knowledge_resolved'
    assert fixed['fields']['identity']['observations'][0]['excluded_source_form_ids']==[10381]
    assert migrated.data['identity_scope_id']=='2026-10-13-M-C'
    assert fixed['fields']['species']['observations']==species_evidence
    assert fixed['fields']['hp']['status']=='manual_verified'
    assert migrated.data['sources']==sources
    assert not migrated.data['complete']
    assert len(TeamConfiguration(data=migrated.data).data['members'][2]['fields']['identity']['observations'])==1


def test_saved_regulation_controls_backfill_and_verified_identity_is_preserved():
    old=json.loads((Path(__file__).parents[1]/'data/teams/my_team.json').read_text())
    old['members'][2]['fields']['identity']['status']='manual_verified'
    old['members'][2]['fields']['identity']['canonical_id']='pokeapi:pokemon:823'
    old['members'][2]['fields']['identity']['value']='pokeapi:pokemon:823'
    old['members'][2]['fields']['identity']['observations']=[{'reviewer':'trainer'}]
    verified=TeamConfiguration(data=old)
    assert verified.data['members'][2]['fields']['identity']['status']=='manual_verified'
    assert verified.data['members'][2]['fields']['identity']['observations']==[{'reviewer':'trainer'}]
    assert verified.data['members'][2]['instance_id']=='own_team_3'
    old['members'][2]['fields']['identity']={
        'value':None,'canonical_id':None,'status':'unknown','confidence':0.0,
        'observations':[],'conflicts':[]}
    other=TeamConfiguration(knowledge=KnowledgeBase(regulation='future'),data=old)
    assert other.data['members'][2]['fields']['identity']['status']=='unknown'
    assert other.data['members'][2]['identity_status']=='species_only'
    assert other.data.get('identity_scope_id')=='2026-10-13-M-C'
    old['identity_scope_id']='previous-M-C-rules'
    previous=TeamConfiguration(data=old)
    assert previous.data['members'][2]['fields']['identity']['status']=='unknown'
