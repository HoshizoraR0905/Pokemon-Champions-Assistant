"""Scoped offline validation; never downloads pages or imports recognition."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from knowledge.champions_stats import ChampionsStats, STATS


def run(snapshots=False):
    folder = ROOT / 'tests/fixtures/champions_stats'
    manifest = json.loads((folder / 'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    fixture = json.loads((folder / '52poke-ranges.json').read_text())
    count = 0
    for case in fixture['cases']:
        model = ChampionsStats(case['identity'], form=case['form'])
        assert model.base_stats == case['base_stats'], case['identity']
        for stat in STATS:
            result = model.attainable(stat, adjustments=['1.0'] if stat == 'hp' else ['0.9','1.0','1.1'])
            assert [result['minimum'], result['maximum']] == case['ranges'][stat], (case['identity'], stat)
            count += 1
        print(case['identity'], 'six published ranges matched', flush=True)
    snapshot_count = 0
    if snapshots:
        rules = json.loads((ROOT / 'knowledge/data/champions_stat_rules.json').read_text())
        for source in rules['sources'] + fixture['sources']:
            raw = (ROOT / source['local_snapshot']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == source['html_sha256'], source['id']
            assert int(re.search(rb'"wgRevisionId":(\d+)', raw)[1]) == source['revision_id']
            snapshot_count += 1
            if source['id'] not in {'charizard','sneasler'}:
                continue
            tables = [m[0] for m in re.finditer(r'<table\b.*?</table>',raw.decode(),re.S)
                      if 'StatPoint' in m[0] and '种族值' in m[0]]
            cases = [c for c in fixture['cases'] if c['source_id'] == source['id']]
            assert len(tables) == len(cases)
            for table, case in zip(tables, cases):
                # Assert the game-specific heading, then read only its columns.
                assert 'Pokémon Champions' in table and '能力点数' in table
                observed = []
                for row in re.findall(r'<tr\b[^>]*>.*?</tr>', table, re.S):
                    cells = re.findall(r'<(?:th|td)\b[^>]*>.*?</(?:th|td)>',row,re.S)
                    selected = [html.unescape(re.sub('<[^>]+>',' ',c)).strip() for c in cells
                                if re.search(r'class="[^"]*\bStatPoint\b',c)]
                    if selected and re.fullmatch(r'\d+ - \d+',selected[0]):
                        assert len(selected) == 2 and selected[1] == '—'
                        observed.append(list(map(int,selected[0].split(' - '))))
                assert observed == [case['ranges'][s] for s in STATS], case['identity']
    result = dict(status='validated',published_stat_ranges=count,source_snapshots_checked=snapshot_count,
                  fixture_manifest_sha256=hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest())
    destination = ROOT / '.cache/champions-stats/validation.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,indent=2)+'\n')
    temporary.replace(destination)
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshots',action='store_true',help='also check existing local HTML snapshots; no network fallback')
    run(parser.parse_args().snapshots)
