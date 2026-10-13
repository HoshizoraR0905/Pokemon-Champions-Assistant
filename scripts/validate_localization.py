"""Spot-check source Chinese names against the official Chinese Pokédex.

Uses HTTPS curl with certificate validation; never runs during recognition.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=Path('knowledge/data'))
    parser.add_argument('--dex',type=int,nargs='+',default=[373,823,903])
    args = parser.parse_args()
    data = json.loads((args.data/'entities.json').read_text())
    entities = {e['species_id']:e for e in data['entities'] if e['form_id'] is None and e['kind']=='species'}
    checks = []
    for number in args.dex:
        url = f'https://dex.pokemon.cn/play/pokedex/{number:04d}'
        raw = subprocess.check_output(['curl','-fsSL','--retry','2',url])
        text = raw.decode('utf-8')
        match = re.search(r'<p class="pokemon-slider__main-name[^"\n]*">([^<]+)</p>',text)
        if not match:
            raise ValueError(f'Official page schema not recognized: {url}')
        expected = entities[number]['names']['zh-hans']
        actual = match[1].strip()
        checks.append({'canonical_id':entities[number]['canonical_id'],'source_name':expected,
                       'official_name':actual,'matches':actual==expected,'url':url,
                       'page_sha256':hashlib.sha256(raw).hexdigest()})
        if actual!=expected:
            raise ValueError(f'Localization mismatch at {url}: {expected} != {actual}')
    (args.data/'validation.json').write_text(json.dumps({'checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Species name spot checks only; no claim of complete translation verification',
        'checks':checks},ensure_ascii=False,indent=2)+'\n')
    print('Official localization checks:',len(checks),'passed')


if __name__=='__main__':
    main()
