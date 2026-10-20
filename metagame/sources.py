"""Current application cache only; historical and simulator endpoints excluded."""
import re

SOURCE_ID = 'championsbattledata'
BASE = 'https://championsbattledata.com'
SOURCE = dict(label='Pokémon Champions Battle Data',
    population='third_party_claimed_ingame_ranked', homepage=BASE,
    guide=BASE+'/api_guide', terms=BASE+'/api-rules/',
    attribution='Battle data provided by Pokémon Champions Battle Data',
    provenance_status='provider_claim; underlying game capture not independently verified',
    sample_count=None, sampling_method=None, weighting=None,
    rate_seconds=2.0)


def source_url(species=None, battle_format='Doubles'):
    if battle_format not in ('Doubles', 'Singles'):
        raise ValueError('Unknown battle format')
    if species is None:
        return BASE+'/api'
    if not re.fullmatch(r'[a-z0-9]+', species):
        raise ValueError('Use an indexed Showdown identifier, not an arbitrary URL')
    return BASE+f'/api/battle/{battle_format}/{species}'
