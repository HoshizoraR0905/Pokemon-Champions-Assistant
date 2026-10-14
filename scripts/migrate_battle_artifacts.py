"""Move known-owned artifacts once; leave relative aliases for historical readers.

Serialized identities, source IDs, event IDs, annotation IDs and state hashes are
immutable. The manifest records namespace ownership separately; no string rewrite.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts


def move_alias(source,target,records):
    if source.is_symlink():
        if source.resolve()!=target.resolve():raise ValueError(f'Conflicting legacy alias: {source}')
        return
    if not source.exists():return
    if target.exists():raise FileExistsError(f'Refusing to overwrite migrated artifact: {target}')
    target.parent.mkdir(parents=True,exist_ok=True)
    checksum=hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
    source.rename(target)
    source.symlink_to(os.path.relpath(target,source.parent),target_is_directory=target.is_dir())
    records.append({'legacy':str(source.relative_to(ROOT)),'canonical':str(target.relative_to(ROOT)),
                    'sha256_before_move':checksum,'identity_policy':'payload unchanged; legacy relative alias'})


def migrate():
    manifest=ROOT/'reports/battle-artifact-migration.json'
    prior=json.loads(manifest.read_text()) if manifest.exists() else {'schema_version':1,'moves':[]}
    records=prior['moves']
    for n in range(5):BattleArtifacts(f'sample_battle_{n}').prepare()
    # Only known-owned directories are moved. OCR weights/venvs/rule KB stay shared.
    for source in list((ROOT/'.cache').iterdir()):
        if source.name.startswith('m223'):move_alias(source,BattleArtifacts('sample_battle_3').cache(source.name),records)
        elif source.name.startswith(('m2-log-','m2-alignment-','m21-')):move_alias(source,BattleArtifacts('sample_battle_2').cache(source.name),records)
        elif source.name.startswith('m15-') and source.suffix=='.log' and not source.name.startswith(('m15-ocr-','m15-coreml-probe')):move_alias(source,BattleArtifacts('sample_battle_1').cache(source.name),records)
        elif source.name=='m15-resolution-178-200':move_alias(source,BattleArtifacts('sample_battle_1').cache(source.name),records)
    for old,battle in [('sample_battle','sample_battle_0'),('sample_battle_1','sample_battle_1')]:
        move_alias(ROOT/'.cache/m14-phases'/old,BattleArtifacts(battle).cache('m14-phases'),records)
    for source in list((ROOT/'reports').iterdir()):
        battle=None
        if source.name.startswith(('M2.2.3','M2.2.4','M2.3.1')):battle='sample_battle_3'
        elif source.name.startswith(('M2.1','M2.2','M2-battle-log')):battle='sample_battle_2'
        elif source.name in ['M1.4-sample-battle-timeline.json','M1.4-final-sample-battle-timeline.json','M1.4-cached-target-review.json'] or source.name=='m15roi-target-window.jsonl':battle='sample_battle_0'
        elif source.name=='M1.4-evidence':battle='sample_battle_1'
        elif source.name in ['M1.4-sample-battle-1-timeline.json','M1.4-final-sample-battle-1-timeline.json'] or source.name.startswith(('m15opt-','m15live-','m15-message-','m15-serial-','m15-workers-','m15roi-move-','m15roi-party-','m15roi-resolution-')):battle='sample_battle_1'
        elif source.name.startswith('M1.5-') and source.suffix=='.json' and source.name not in ['M1.5-focused-rois.json','M1.5-phase-compatibility.json','M1.5-coreml-probe.json'] and not source.name.startswith('M1.5-ocr-'):battle='sample_battle_1'
        if battle:move_alias(source,BattleArtifacts(battle).report(source.name),records)
    for source in (ROOT/'reports/archive').glob('M1.4-final-sample-battle*-timeline-before-banner-review.json'):
        battle='sample_battle_1' if 'sample-battle-1-' in source.name else 'sample_battle_0'
        move_alias(source,BattleArtifacts(battle).report('archive/'+source.name),records)
    for filename,battle in [('targets.png','sample_battle_0'),('moves.png','sample_battle_1'),('party.png','sample_battle_1'),('replacement.png','sample_battle_1')]:
        move_alias(ROOT/'reports/M1.5-roi-evidence'/filename,BattleArtifacts(battle).report('M1.5-roi-evidence/'+filename),records)
    for battle,source,name in [
        ('sample_battle_1','tests/fixtures/m14_selection_context.json','m14_selection_context.json'),
        ('sample_battle_2','tests/fixtures/m21_battle_log_ground_truth.json','m21_battle_log_ground_truth.json'),
        ('sample_battle_2','tests/fixtures/m22_initial_context.json','m22_initial_context.json'),
        ('sample_battle_3','tests/fixtures/m223_initial_context.json','m223_initial_context.json'),
        ('sample_battle_3','tests/fixtures/m223_annotations.json','m223_annotations.json'),
        ('sample_battle_3','data/teams/sample_battle_3_opening.json','opening_team.json')]:
        move_alias(ROOT/source,BattleArtifacts(battle).input(name),records)
    truth=ROOT/'tests/fixtures/m14_phase_ground_truth.json'
    if truth.exists():
        for recording,annotations in json.loads(truth.read_text())['videos'].items():
            paths=BattleArtifacts.select(video=recording).prepare();destination=paths.input('m14_phase_annotations.json')
            destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.exists():destination.write_text(json.dumps({'battle_id':paths.battle_id,'legacy_recording_key':recording,'annotations':annotations,'source_fixture':'tests/fixtures/m14_phase_ground_truth.json'},ensure_ascii=False,indent=2)+'\n')
    empty_context=BattleArtifacts('sample_battle_0').input('m14_selection_context.json')
    empty_context.parent.mkdir(parents=True,exist_ok=True)
    if not empty_context.exists():empty_context.write_text('[]\n')
    # Original recording already renamed by the user: old source IDs remain resolvable.
    old=ROOT/'tests/fixtures/sample_battle.mp4';new=ROOT/'tests/fixtures/sample_battle_0.mp4'
    if new.exists() and not old.exists():old.symlink_to(new.name)
    for n in range(5):
        paths=BattleArtifacts(f'sample_battle_{n}');video=paths.video();index=paths.report('battle.json')
        if index.exists() and json.loads(index.read_text())['battle_id']!=paths.battle_id:raise ValueError('Recording manifest ownership mismatch')
        index.write_text(json.dumps({'schema_version':1,'battle_id':paths.battle_id,'video':str(video.relative_to(ROOT)),'size_bytes':video.stat().st_size,
            'cache_directory':str(paths.cache_dir.relative_to(ROOT)),'report_directory':str(paths.report_dir.relative_to(ROOT)),
            'legacy_identity_aliases':['sample_battle'] if n==0 else [],'migration_policy':'historical payload identities retained'},indent=2)+'\n')
    prior.update(video_aliases={'sample_battle.mp4':'sample_battle_0.mp4'},
       canonical_id_aliases={'sample_battle':'sample_battle_0'},
       user_authorized_video_rename={'sample_battle_5.mp4':'sample_battle_4.mp4'},
       preserved_identifiers=True,unresolved=['Mixed-battle M1 summaries/evidence remain shared pending per-observation attribution'])
    manifest.write_text(json.dumps(prior,ensure_ascii=False,indent=2)+'\n')
    return prior

if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args();print(f'{len(migrate()["moves"])} migrated paths; no video/OCR processing')
