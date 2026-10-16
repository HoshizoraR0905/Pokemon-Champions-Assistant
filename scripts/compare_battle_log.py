"""Pass B only: independent historical extraction after a verified Pass A seal."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import cv2
from battle_artifacts import BattleArtifacts,canonical_id
from recognition.video_sampling import atomic_json
from recognition.event_report import verify_seal,write_viewer
from recognition.fast_video import CachedOCR,digest
from recognition.fast_profile import normalized,RegionGate
from recognition.battle_log import detect_log,extract_view,assemble_views
from recognition.log_comparison import align
from battle_events.parser import EventParser


def compare(paths,run_id,*,resume=False,reference_cache=None):
    run_id=canonical_id(run_id);folder=paths.cache('event-driven/'+run_id);report=paths.report('event-driven/'+run_id)
    seal=verify_seal(folder)
    if seal['battle_id']!=paths.battle_id:raise ValueError('Prediction belongs to another battle')
    reference=folder/'reference';reference.mkdir(exist_ok=True)
    manifest_path=reference/'manifest.json'
    source_paths=[Path(__file__),ROOT/'recognition/battle_log.py',ROOT/'recognition/log_comparison.py',ROOT/'battle_events/parser.py',ROOT/'battle_events/visible_endings.py',ROOT/'recognition/event_report.py',ROOT/'scripts/templates/event_review.html']
    identity=dict(prediction_sha256=seal['files']['video-only.json'],sources={str(p.relative_to(ROOT)):digest(p) for p in source_paths})
    cached_reference=None
    if reference_cache:
        refpath=Path(reference_cache).resolve()
        if not refpath.is_relative_to(paths.cache_dir.resolve()):raise ValueError('Reference cache belongs outside this battle')
        cached_reference=json.loads(refpath.read_text());paths.check_identity(cached_reference['battle_id'])
        old=json.loads((refpath.parent/'manifest.json').read_text())
        if old['identity']['sources']['recognition/battle_log.py']!=identity['sources']['recognition/battle_log.py']:
            raise ValueError('Historical extractor changed; cannot reuse views')
        parent=json.loads((refpath.parent.parent/'manifest.json').read_text())
        current=json.loads((folder/'manifest.json').read_text())
        if parent['identity']['video_sha256']!=current['identity']['video_sha256']:raise ValueError('Reference video mismatch')
        identity['reference_cache']=dict(path=str(refpath),sha256=digest(refpath))
    prior=json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    if prior and prior['identity']!=identity:raise ValueError('Reference implementation changed; preserve previous reference stage')
    if prior and not resume:raise ValueError('Reference stage exists; use --resume')
    if prior and prior['status']=='complete':return prior
    began=time.monotonic();counts=Counter();ocr=CachedOCR(reference,counts)
    # Use the same model; no fuzzy reuse across different historical row positions.
    rows=json.loads((folder/'observations.json').read_text())['observations']
    views=deepcopy(cached_reference['views']) if cached_reference else [];gate=RegionGate(.004)
    if cached_reference:counts['reference_views_reused']=len(views)
    manifest=dict(status='running',identity=identity,started_at=datetime.now(timezone.utc).isoformat(),
        prediction_frozen_at=seal['frozen_at'],event_time_policy='log inspection timestamps never represent original event time')
    atomic_json(manifest_path,manifest)
    try:
        for n,row in enumerate([] if cached_reference else rows):
            if row['ui'].get('overlay')!='battle_log_overlay':continue
            path=reference/'views'/f'{n:06d}.json'
            if path.exists():
                view=json.loads(path.read_text());views.append(view);counts['completed_views_reused']+=1;continue
            image=cv2.imread(str(paths.root/row['image']));geometry=detect_log(image)
            if not geometry:continue
            sig=normalized(image,geometry['panel'],text=True)
            chosen,reason,_=gate.choose('historical_page',sig,True,row['timestamp'])
            if not chosen:counts['unchanged_log_frames_skipped']+=1;continue
            ocr.source=row['source_id'];ocr.timestamp=row['timestamp'];ocr.gate=RegionGate(.004)
            view=extract_view(image,ocr,row['source_id'],row['timestamp'],row['sha256'])
            view['image']=row['image'];view['frame_sha256']=row['sha256'];view['original_event_time']=None
            atomic_json(path,view);views.append(view);gate.store('historical_page',sig,row['timestamp'],{},row['source_id'])
            manifest.update(completed_views=len(views),counts=dict(counts),last_inspection_timestamp=row['timestamp'])
            atomic_json(manifest_path,manifest)
            print(f'Pass B: inspection {row["timestamp"]:.3f}s, {len(view["observations"])} historical row observations',flush=True)
        entries,issues=assemble_views(views,ignore_partial_overlap=True)
        observations={r['observation_id']:r for v in views for r in v['observations']}
        for entry in entries:
            selected=observations[entry['selected_observation_id']]
            entry.update(partial=selected['partial'],inspection_timestamp=selected['timestamp'],
                         original_event_time=None,scroll_provenance=[dict(source_id=v['source_id'],inspection_timestamp=v['timestamp'],
                             scroll_top=v['geometry']['scroll_top'],scroll_height=v['geometry']['scroll_height'])
                             for v in views if any(r['observation_id'] in entry['observation_ids'] for r in v['observations'])])
        parser=EventParser();events=[parser.parse(e,battle_id=paths.battle_id).to_dict() for e in entries]
        prediction=json.loads((folder/'video-only.json').read_text());comparison=align(entries,events,prediction['events'])
        frames=json.loads((report/'frames.json').read_text());by_source={f['source_id']:f for f in frames}
        for c in comparison['comparisons']:
            sources={observations[oid]['source_id'] for oid in c['log_observation_ids']}
            c['log_frames']=[by_source[s] for s in sorted(sources) if s in by_source]
        raw=dict(battle_id=paths.battle_id,prediction_sha256=identity['prediction_sha256'],views=views,
            entries=entries,event_candidates=events,assembly_issues=issues,whole_match_coverage_established=False,
            observed_turns=sorted({e['turn'] for e in entries if e['turn'] is not None}))
        atomic_json(reference/'battle-log.json',raw);atomic_json(report/'battle-log.json',raw)
        atomic_json(report/'log-comparison.json',comparison)
        summary=json.loads((report/'summary.json').read_text())
        monitoring=json.loads((report/'monitoring.json').read_text())
        write_viewer(report,dict(summary=summary,prediction=prediction,frames=frames,monitoring=monitoring,reference=raw,comparison=comparison))
        manifest.update(status='complete',active_seconds=time.monotonic()-began,counts=dict(counts),
            observed_log_entries=len(entries),observed_turns=raw['observed_turns'],assembly_issues=len(issues),summary=comparison['summary'])
        atomic_json(manifest_path,manifest)
        verify_seal(folder)
        return manifest
    except BaseException as exc:
        manifest.update(status='failed',error=repr(exc),active_seconds=time.monotonic()-began,counts=dict(counts))
        atomic_json(manifest_path,manifest);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle-id',required=True);p.add_argument('--run-id',required=True);p.add_argument('--resume',action='store_true');p.add_argument('--reference-cache',type=Path)
    a=p.parse_args();print(json.dumps(compare(BattleArtifacts(a.battle_id,ROOT),a.run_id,resume=a.resume,reference_cache=a.reference_cache),ensure_ascii=False,indent=2))
