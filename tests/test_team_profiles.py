from copy import deepcopy
import json
import pytest
from team_configuration import TeamConfiguration, REQUIRED, STATS
from team_configuration.profiles import TeamProfiles


def verified_team():
    team=TeamConfiguration(team_id='same-roster')
    for i in range(1,7):
        slot=f'own_team_{i}'
        values=dict(species='pokeapi:species:823',identity='pokeapi:pokemon:823',
                    ability='pokeapi:ability:46',held_item='pokeapi:item:234',
                    **{f'move_{n}':'pokeapi:move:182' for n in range(1,5)})
        for name in REQUIRED:
            args={'value':100} if name in STATS else {'canonical_id':values[name]}
            team.correct(slot,name,reviewer='trainer',**args)
    return team


def test_build_ids_same_roster_independent_retrieval_and_no_overwrite(tmp_path):
    profiles=TeamProfiles(tmp_path);team=verified_team()
    profiles.register('build-a',team,reviewer='trainer')
    team.correct('own_team_1','speed',value=101,reviewer='trainer')
    profiles.register('build-b',team,reviewer='trainer')
    assert len(profiles.list())==2
    assert profiles.load('build-a').data['members'][0]['fields']['speed']['value']==100
    assert profiles.load('build-b').data['members'][0]['fields']['speed']['value']==101
    loaded=profiles.load('build-a');loaded.data['members'][0]['fields']['speed']['value']=999
    assert profiles.load('build-a').data['members'][0]['fields']['speed']['value']==100
    with pytest.raises(FileExistsError):profiles.register('build-a',team,reviewer='trainer')


def test_incomplete_conflicting_and_unverified_optional_stay_unknown(tmp_path):
    profiles=TeamProfiles(tmp_path)
    with pytest.raises(ValueError):profiles.register('incomplete',TeamConfiguration(),reviewer='trainer')
    team=verified_team();team.data['members'][0]['fields']['nature'].update(value='guess',status='observed')
    before=deepcopy(team.data)
    profiles.register('clean',team,reviewer='trainer')
    assert profiles.load('clean').data['members'][0]['fields']['nature']['value'] is None
    assert team.data==before
    team.data['members'][0]['fields']['hp']['conflicts'].append(dict(resolved=False))
    with pytest.raises(ValueError):profiles.register('conflict',team,reviewer='trainer')


def test_path_and_tampered_content_rejected(tmp_path):
    profiles=TeamProfiles(tmp_path)
    with pytest.raises(ValueError):profiles.load('../escape')
    path=profiles.register('valid',verified_team(),reviewer='trainer')
    data=json.loads(path.read_text());data['configuration']['members'][0]['fields']['hp']['value']=999
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):profiles.load('valid')


def test_complete_flag_cannot_certify_empty_or_malformed_required_values(tmp_path):
    profiles=TeamProfiles(tmp_path);team=verified_team()
    team.data['members'][0]['fields']['hp']['value']=None
    with pytest.raises(ValueError):profiles.register('empty-hp',team,reviewer='trainer')
    team=verified_team();team.data['members'][0]['fields']['ability']['canonical_id']='pokeapi:move:182'
    with pytest.raises(ValueError):profiles.register('wrong-kind',team,reviewer='trainer')
