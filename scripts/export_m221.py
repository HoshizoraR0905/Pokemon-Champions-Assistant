"""Generate a standalone viewer from serialized M2.2 history and snapshots."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracking.state_timeline import build_timeline, render_html

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=Path, default=ROOT/'reports/M2.2-battle-state.json',
                        help='M2.2 serialized engine containing history and initial_state')
    parser.add_argument('--initial', type=Path, help='Optional fixture wrapper or raw initial state')
    parser.add_argument('--snapshots', type=Path, default=ROOT/'reports/M2.2-state-snapshots.json')
    parser.add_argument('--output', type=Path, default=ROOT/'reports/M2.2.1-state-timeline.html')
    parser.add_argument('--json-output', type=Path, default=ROOT/'reports/M2.2.1-state-timeline.json')
    args = parser.parse_args()
    saved = json.loads(args.history.read_text())
    initial = json.loads(args.initial.read_text()) if args.initial else saved['initial_state']
    initial = initial.get('state', initial)
    snapshots = json.loads(args.snapshots.read_text())
    timeline = build_timeline(saved['history'], initial, snapshots['snapshots'], saved.get('state'))
    args.output.write_text(render_html(timeline), encoding='utf-8')
    args.json_output.write_text(json.dumps(timeline, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'{len(timeline["entries"])-1} events exported to {args.output}')


if __name__ == '__main__':
    main()
