"""Package the scoped message-identity experiment without running recognition."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.event_report import verify_seal
from recognition.video_sampling import atomic_json


def read(path):return json.loads(path.read_text())


def build(owner,run_id,evaluation_id):
    source=owner.cache('event-driven/'+run_id);target=owner.cache('evaluation/'+evaluation_id)
    verify_seal(source)
    comparison=read(target/'comparisons.json'); frozen=target/'message-predictions.json'
    assert digest(frozen)==comparison['frozen_predictions_sha256']
    assert digest(source/'video-only.json')==comparison['source_sha256']
    replay=read(source/'replay.json');manifest=read(source/'manifest.json')
    execution=read(owner.cache('evaluation/'+run_id+'/execution.json'))
    for name,sha in execution['sealed_outputs'].items():assert digest(source/name)==sha
    work=read(target/'identity-work.json');c=manifest['counts']
    episodes=replay['state']['knowledge']['active_entry_episodes']
    baseline=[]
    for p in comparison['rows']:
        ep=next((e for e in episodes if e['episode_id']==p.get('episode_id')),None)
        if not ep:
            matches=[e for e in episodes if e['start']==p['timestamp'] and e['side']==p['side']]
            ep=matches[0] if len(matches)==1 else {}
        ep=ep or {};binding=ep.get('hud_binding',{})
        baseline.append(dict(timestamp=p['timestamp'],side=ep.get('side'),slot=ep.get('slot'),
            species_id=ep.get('species_id'),hud_binding_status=binding.get('status'),
            verified_at=binding.get('resolved_at'),episode_id=ep.get('episode_id')))
    status='INCONCLUSIVE_MORE_EVIDENCE_REQUIRED'
    performance=dict(wall_seconds=execution['wall_seconds'],video_seconds=manifest['decoder']['container_duration_seconds'],
        processing_to_video_ratio=execution['wall_seconds']/manifest['decoder']['container_duration_seconds'],
        video_to_processing_ratio=manifest['decoder']['container_duration_seconds']/execution['wall_seconds'],
        peak_sampled_process_tree_rss_mib=execution['peak_process_tree_rss_mb'],
        total_ocr_inferences=c['ocr_invocations_performed'],total_ocr_seconds=c['ocr_seconds'],
        total_icon_profile_inferences=c['icon_invocations_performed'],total_icon_seconds=c['icon_seconds'],
        identity_work={k:v for k,v in work.items() if k!='requests'})
    review=dict(status=status,independent_human_ground_truth=False,observable_arrivals=8,
        reviewed_message_band_sheets=20,reviewed_visual_representatives=389,
        recorded_message_band_review='All eight recognized send-outs image-reviewed; 389 changed message-band representatives inspected from 95s to recording end. Not full source-frame annotation.',
        limitations=['Two message-only entries have unresolved logical slots after an unrecognized withdrawal at 294s; later HUD cannot supply prediction slots.',
                     'Three message names leave forms ambiguous; five form comparisons remain inconclusive.',
                     'No custom nickname or foreign Pokemon-name normalization challenge is established by this single opponent.',
                     'Sampling is 2 FPS, with confirmed COMMAND inspections at 1 FPS. Uninspected/unsampled frames have not been exhaustively annotated.'],
        decision='Do not implement message_primary or disable production identity acquisition on this evidence. Keep the existing production mode and optional W path unchanged.')
    data=dict(comparison=comparison,baseline=baseline,performance=performance,review=review)
    report=owner.report('evaluation/'+evaluation_id);report.mkdir(parents=True,exist_ok=True)
    def evidence_image(evidence):
        for e in evidence:
            image=e.get('details',{}).get('image')
            if image:
                p=(ROOT/image).resolve();assert p.is_relative_to(owner.cache_dir.resolve())
                return os.path.relpath(p,report)
    for r in data['comparison']['rows']:
        r['message_image']=evidence_image(r['evidence'])
        r['hud_image']=evidence_image((r.get('hud') or {}).get('evidence',[]))
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(ROOT/'scripts/templates/message_identity.html').read_text()
    (report/'review.html').write_text(template.replace('__DATA__',payload))
    atomic_json(target/'acceptance.json',data)
    atomic_json(target/'report-manifest.json',dict(status='complete',decision=status,
        inputs={str(p.relative_to(ROOT)):digest(p) for p in [frozen,target/'comparisons.json',target/'identity-work.json',source/'manifest.json',source/'replay.json']},
        outputs={str(report/'review.html'):digest(report/'review.html')},
        sources={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'scripts/templates/message_identity.html']}))
    print(json.dumps(dict(decision=status,performance=performance,counts=comparison['counts'],baseline=baseline),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True);p.add_argument('--run-id',required=True);p.add_argument('--evaluation-id',required=True)
    a=p.parse_args();build(BattleArtifacts(a.battle),a.run_id,a.evaluation_id)
