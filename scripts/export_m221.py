"""Generate a standalone viewer from serialized M2.2 history and snapshots."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from battle_artifacts import BattleArtifacts, add_arguments
from tracking.state_timeline import build_timeline, render_html

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=Path,
                        help='M2.2 serialized engine containing history and initial_state')
    parser.add_argument('--initial', type=Path, help='Optional fixture wrapper or raw initial state')
    parser.add_argument('--snapshots', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--json-output', type=Path)
    add_arguments(parser)
    args = parser.parse_args()
    paths=BattleArtifacts.select(args.battle_id,args.video,default='sample_battle_2').prepare()
    args.history=args.history or paths.report('M2.2-battle-state.json')
    args.snapshots=args.snapshots or paths.report('M2.2-state-snapshots.json')
    explicit_output=args.output is not None
    saved = json.loads(args.history.read_text())
    initial = json.loads(args.initial.read_text()) if args.initial else saved['initial_state']
    initial = initial.get('state', initial)
    if args.battle_id or args.video:paths.check_identity(initial['battle_id'])
    else:paths=BattleArtifacts(initial['battle_id']).prepare()
    args.output=paths.guard_output(args.output or paths.report('M2.2.1-state-timeline.html'))
    args.json_output=paths.guard_output(args.json_output or paths.report('M2.2.1-state-timeline.json'))
    snapshots = json.loads(args.snapshots.read_text())
    timeline = build_timeline(saved['history'], initial, snapshots['snapshots'], saved.get('state'))
    if 'mechanic_rules' in saved:
        timeline['mechanic_rules']=saved['mechanic_rules']
    timeline['artifact_root']=os.path.relpath(ROOT,args.output.resolve().parent)+'/'
    args.output.resolve().write_text(render_html(timeline), encoding='utf-8')
    args.json_output.resolve().write_text(json.dumps(timeline, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'{len(timeline["entries"])-1} events exported to {args.output}')


if __name__ == '__main__':
    main()
