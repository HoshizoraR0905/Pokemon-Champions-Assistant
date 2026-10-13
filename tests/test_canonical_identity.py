"""Pinned PokéAPI variant/form keys and identity conservatism."""
from dataclasses import replace
import json
from pathlib import Path

from knowledge import KnowledgeBase
from models import IconCandidate, IconEvidence, Observation
from recognition.entities import EntityResolver
from recognition.identity import combine_identity
from team_configuration import TeamConfiguration


def test_verified_upstream_variant_ids_and_null_forms():
    kb=KnowledgeBase()
    cases={
        6:(6,6,'pokeapi:pokemon:6'),
        10134:(6,10034,'pokeapi:pokemon:10034'),
        10135:(6,10035,'pokeapi:pokemon:10035'),
        26:(26,26,'pokeapi:pokemon:26'),
        10202:(26,10100,'pokeapi:pokemon:10100'),
        876:(876,876,'pokeapi:pokemon:876'),
        10355:(876,10186,'pokeapi:pokemon:10186'),
    }
    for source_form,(species,pokemon,key) in cases.items():
        actual=kb.identities.for_form(source_form)
        assert (actual['species_id'],actual['pokemon_id'],actual['canonical_identity'])==(species,pokemon,key)
        assert actual['form_id'] is None
        assert kb.identities.for_key(key)==actual
    assert kb.identities.for_form(10346)['canonical_identity']=='pokeapi:form:10346'
    assert kb.identities.for_form(10346)['form_id']==10346
    assert kb.identities.for_key('pokeapi:pokemon:869')['identity_status']=='unresolved'


def test_species_only_does_not_default_to_base_or_male():
    resolver=EntityResolver()
    for name,sid in [('雷丘',26),('爱管侍',876),('喷火龙',6)]:
        obs=resolver.resolve(Observation(name,.99,raw_text=name),'species',region_kind='species')
        assert obs.resolution.species_id==sid
        assert obs.resolution.identity_status=='species_only'
        assert obs.resolution.canonical_identity is None
        assert obs.resolution.pokemon_id is None


def test_identity_snapshot_unique_and_referentially_consistent():
    kb=KnowledgeBase()
    forms=kb.identity['forms']
    keys=[r['canonical_identity'] for r in forms]
    assert len(keys)==len(set(keys))==len(forms)
    for row in forms:
        expected=kb.identities.for_form(row['source_form_id'])
        assert all(row[k]==expected[k] for k in ('species_id','pokemon_id','form_id',
                                                 'canonical_identity','identity_status'))
        assert f"pokeapi:species:{row['species_id']}" in kb.entities
    visual=json.loads((Path(__file__).parents[1]/'knowledge/data/visual_assets.json').read_text())['assets']
    for asset in visual:
        if asset['source_form_id'] is None:
            assert asset['canonical_identity'] is None
        else:
            expected=kb.identities.for_form(asset['source_form_id'])
            assert asset['species_id']==expected['species_id']
            assert asset['canonical_identity']==expected['canonical_identity']
    by_file={r['file']:r for r in visual}
    assert by_file['raichu.png']['canonical_identity']=='pokeapi:pokemon:26'
    assert by_file['raichu-alola.png']['canonical_identity']=='pokeapi:pokemon:10100'
    assert by_file['charizard-mega-x.png']['canonical_identity']=='pokeapi:pokemon:10034'
    assert by_file['charizard-mega-y.png']['canonical_identity']=='pokeapi:pokemon:10035'
    assert by_file['indeedee.png']['canonical_identity']=='pokeapi:pokemon:876'
    assert by_file['indeedee-female.png']['canonical_identity']=='pokeapi:pokemon:10186'


def test_text_and_visual_variant_fusion_requires_unique_identity():
    kb=KnowledgeBase();resolver=EntityResolver(kb)
    text=resolver.resolve(Observation('雷丘',.99,raw_text='雷丘'),'species',region_kind='species')
    base=IconEvidence(status='resolved',species_id=26,pokemon_id=26,form_id=None,
        canonical_id='pokeapi:species:26',canonical_identity='pokeapi:pokemon:26')
    alola=replace(base,pokemon_id=10100,canonical_id='pokeapi:form:10202',
                  canonical_identity='pokeapi:pokemon:10100')
    assert combine_identity(text,base,kb).resolution.canonical_identity=='pokeapi:pokemon:26'
    assert combine_identity(text,alola,kb).resolution.canonical_identity=='pokeapi:pokemon:10100'
    ambiguous=IconEvidence(status='ambiguous',species_id=26,reason='forms_visually_ambiguous',
        candidates=[IconCandidate('pokeapi:species:26',26,None,'raichu.png',.88,.8,(0,0),26,'pokeapi:pokemon:26'),
                    IconCandidate('pokeapi:form:10202',26,None,'raichu-alola.png',.86,.8,(0,0),10100,'pokeapi:pokemon:10100')])
    assert combine_identity(text,ambiguous,kb).resolution.identity_status=='species_only'


def test_team_instance_stays_stable_when_identity_evidence_conflicts():
    kb=KnowledgeBase();team=TeamConfiguration(kb)
    member=team.data['members'][0]
    team.correct('own_team_1','species',canonical_id='pokeapi:species:6',reviewer='trainer')
    team.correct('own_team_1','identity',canonical_id='pokeapi:pokemon:6',reviewer='trainer')
    assert member['instance_id']=='own_team_1'
    assert member['canonical_identity']=='pokeapi:pokemon:6'
    # A later configuration observation must retain the same instance and
    # surface the form change as evidence, not silently rewrite its identity.
    from models import EntityResolution, Pokemon, Recognition
    obs=Observation('Mega Charizard X',.99,raw_text='Mega Charizard X',
        resolution=EntityResolution(canonical_id='pokeapi:form:10134',species_id=6,
            pokemon_id=10034,canonical_identity='pokeapi:pokemon:10034',
            identity_status='resolved_variant',status='resolved'))
    team.ingest(Recognition('synthetic',0,0,screen='team_configuration',
        pokemon=[Pokemon('own_team_1',obs)]))
    assert member['instance_id']=='own_team_1'
    assert member['canonical_identity']=='pokeapi:pokemon:6'
    assert 'identity' in member['conflicting_fields']


def test_team_snapshot_preserves_ambiguous_variant_candidates():
    from models import Pokemon, Recognition
    resolver=EntityResolver()
    text=resolver.resolve(Observation('雷丘',.99,raw_text='雷丘'),'species',region_kind='species')
    icon=IconEvidence(status='ambiguous',species_id=26,reason='forms_visually_ambiguous',
        candidates=[IconCandidate('pokeapi:species:26',26,None,'raichu.png',.88,.8,(0,0),26,'pokeapi:pokemon:26'),
                    IconCandidate('pokeapi:form:10202',26,None,'raichu-alola.png',.86,.8,(0,0),10100,'pokeapi:pokemon:10100')])
    team=TeamConfiguration()
    team.ingest(Recognition('synthetic',0,0,screen='team_configuration',
        pokemon=[Pokemon('own_team_1',text,icon=icon)]))
    member=team.data['members'][0]
    assert member['identity_status']=='ambiguous_variant'
    assert member['canonical_identity'] is None
    assert member['fields']['identity']['observations'][0]['candidate_ids']==[
        'pokeapi:pokemon:10100','pokeapi:pokemon:26']
