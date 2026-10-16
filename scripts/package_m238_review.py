"""Refresh presentation from sealed M2.3.8 predictions/reference; no recognition."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts,canonical_id
from recognition.fast_video import digest
from recognition.event_report import verify_seal,write_viewer
from recognition.video_sampling import atomic_json


def package(paths,run_id):
    began=time.monotonic();run_id=canonical_id(run_id)
    folder=paths.cache('event-driven/'+run_id);report=paths.report('event-driven/'+run_id)
    seal=verify_seal(folder)
    if digest(report/'video-only.json')!=seal['files']['video-only.json']:raise ValueError('Report prediction does not match its seal')
    target=report/'review.html'
    if target.exists():
        archive=folder/'viewer-archive'/f'{digest(target)}.html';archive.parent.mkdir(exist_ok=True)
        if not archive.exists():shutil.copy2(target,archive)
    def read(name):return json.loads((report/name).read_text())
    data=dict(summary=read('summary.json'),prediction=read('video-only.json'),frames=read('frames.json'),monitoring=read('monitoring.json'),
        reference=read('battle-log.json') if (report/'battle-log.json').exists() else None,
        comparison=read('log-comparison.json') if (report/'log-comparison.json').exists() else None)
    write_viewer(report,data)
    manifest=dict(status='complete',prediction_sha256=seal['files']['video-only.json'],html_sha256=digest(target),
        template_sha256=digest(ROOT/'scripts/templates/event_review.html'),renderer_sha256=digest(ROOT/'recognition/event_report.py'),
        source_summary_sha256=digest(report/'summary.json'),active_seconds=time.monotonic()-began,
        annotation_policy='Notes are external and keyed by frozen prediction hash; no runtime corrections.')
    atomic_json(folder/'viewer-packaging.json',manifest);verify_seal(folder)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle-id',required=True);p.add_argument('--run-id',required=True)
    a=p.parse_args();print(json.dumps(package(BattleArtifacts(a.battle_id,ROOT),a.run_id),indent=2))
