"""Re-export saved offline HTML with lossless sharing; no battle/media replay."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from tracking.state_timeline import render_html, unpack_timeline

MARKER='<script type="application/json" id="timeline-data">'


def payload(html):
    start=html.index(MARKER)+len(MARKER)
    return json.loads(html[start:html.index('</script>',start)])


def optimize(source, destination):
    started=time.perf_counter()
    original=source.read_text()
    timeline=unpack_timeline(payload(original))
    paths=BattleArtifacts(timeline['battle_id'])
    destination=paths.guard_output(destination).resolve()
    timeline={**timeline,'artifact_root':os.path.relpath(ROOT,destination.resolve().parent)+'/'}
    result=render_html(timeline)
    # Every state, raw difference, observation and provenance is preserved.
    if unpack_timeline(payload(result)) != timeline:
        raise ValueError('Compact export differs from original timeline')
    temp=destination.with_suffix(destination.suffix+'.tmp')
    temp.write_text(result);temp.replace(destination)
    return {'source':str(source),'output':str(destination),'states':len(timeline['entries']),
            'before_bytes':len(original.encode()),'after_bytes':len(result.encode()),
            'lossless_round_trip':True,'export_seconds':round(time.perf_counter()-started,2)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    print(json.dumps(optimize(args.source,args.output or args.source),ensure_ascii=False))
