"""Validation-method regressions; no recognition or video decoding."""
import json
from pathlib import Path
import pytest
from scripts.evaluate_m233c import hud_score
from scripts.validate_m233c import ValidationPaths

ROOT=Path(__file__).resolve().parents[1]

def test_numeric_hp_match_on_wrong_species_is_not_correctly_attributed():
 label=dict(slots=[dict(side='opponent',slot='left',species_id=903,hp=dict(percent=100))])
 state=dict(sides={'opponent':dict(active_slots=dict(left='p'))},pokemon={'p':dict(species=dict(value=dict(species_id=936)),hp=dict(observations=[dict(unit='displayed_percent',after=100)]))})
 result=hud_score(label,state)[0]
 assert result['hp']=='correct' and result['identity']=='incorrect'
 assert result['attributed_hp']=='incorrect'


def test_validation_cache_namespace_preserves_historical_paths():
 paths=ValidationPaths('sample_battle_2')
 assert '/m233c/measurement/ocr/' in str(paths.cache('m233b1/ocr/example.json'))
 assert str(paths.cache('m232/observations.json')).endswith('/m232/observations.json')


def test_review_labels_cover_positive_negative_and_uncertain_cases():
 data=json.loads((ROOT/'tests/fixtures/battles/m233c_semantic_review.json').read_text())
 assert {r['battle_id'] for r in data['hud_checkpoints']}=={f'sample_battle_{i}' for i in range(5)}
 for interval in data['intervals']:
  assert {r['label'] for r in interval['frames']}=={'clear_message','no_message','ambiguous_fade'}
  assert all(o['target'] is None for o in interval['occurrences'])
  assert all('sha256' in r and 'image' in r for r in interval['frames'])

@pytest.mark.local_artifacts('.cache/m233c/results.json')
def test_scored_prefixes_exclude_reviewed_frame_evidence():
 data=json.loads((ROOT/'tests/fixtures/battles/m233c_semantic_review.json').read_text())
 for i in range(5):
  bid=f'sample_battle_{i}';p=ROOT/f'.cache/battles/{bid}/m233c/replay-current.json'
  d=json.loads(p.read_text());hashes={q['sha256'] for q in data['hud_checkpoints'] if q['battle_id']==bid}
  assert set(d['excluded_frame_hashes'])==hashes
  for value in d['prefixes'].values():
   # Fact provenance cannot include a held-out checkpoint image hash.
   encoded=json.dumps(value['state'])
   assert all(h not in encoded for h in hashes)
