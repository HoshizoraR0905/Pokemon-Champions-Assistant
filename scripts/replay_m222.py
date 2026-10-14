"""Replay cached M2.1 evidence with M2.2.2 mechanic state; preserve legacy artifacts."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.replay_m22 import run, ROOT
from tracking.mechanic_rules import showdown_champions_reference
from battle_artifacts import BattleArtifacts, add_arguments, check_event_ownership
from tracking.state_timeline import build_timeline, render_html


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events',type=Path)
    p.add_argument('--initial',type=Path)
    p.add_argument('--output-prefix',type=Path)
    p.add_argument('--rules-profile',choices=['evidence-only','showdown-reference'],default='evidence-only',
                   help='Reference opts into simulator rules, not official Champions verification')
    add_arguments(p)
    a=p.parse_args();paths=BattleArtifacts.select(a.battle_id,a.video,default='sample_battle_2').prepare()
    a.events=a.events or paths.report('M2.1-battle-log-events.json')
    a.initial=a.initial or paths.input('m22_initial_context.json')
    paths.check_identity(json.loads(a.initial.read_text())['state']['battle_id'])
    a.output_prefix=paths.guard_output(a.output_prefix or paths.report('M2.2.2'))
    check_event_ownership(paths,json.loads(a.events.read_text()))
    rules=showdown_champions_reference() if a.rules_profile=='showdown-reference' else None
    engine,snapshots=run(a.events,a.initial,mechanic_rules=rules)
    timeline=build_timeline(engine.to_dict()['history'],engine.initial.to_dict(),snapshots,engine.state.to_dict())
    timeline['mechanic_rules']=engine.mechanic_rules.to_dict()
    for suffix,payload in [('battle-state',engine.to_dict()),('state-snapshots',{'schema_version':2,'snapshots':snapshots}),
                           ('decision-state',engine.decision_state())]:
        Path(str(a.output_prefix)+'-'+suffix+'.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    Path(str(a.output_prefix)+'-state-timeline.html').write_text(render_html(timeline,artifact_root='../../../'))
    print(f'{len(engine.history)} events; profile {engine.mechanic_rules.profile_id}; final hash {engine.to_dict()["state_hash"]}')


if __name__=='__main__': main()
