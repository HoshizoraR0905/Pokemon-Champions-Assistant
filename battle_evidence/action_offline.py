"""Scoped, fingerprinted action analysis over immutable v2.2 artifacts."""
from pathlib import Path
import json
import time
from collections import Counter
from battle_artifacts import BattleArtifacts
from speed_inference.offline import atomic_json,file_hash
from speed_inference.domains import digest
from team_configuration import TeamConfiguration
from .actions import reconstruct,VERSION
from .action_inference import analyse
from .builds import KnownBuilds

ROOT=Path(__file__).resolve().parents[1]


def inputs_for(battle):
    visual=battle.cache('m34-visual-v22/visual-evidence.json')
    visual_manifest=visual.with_name('manifest.json')
    seal=json.loads(visual_manifest.read_text())
    if seal.get('status')!='complete' or seal.get('output_hash')!=file_hash(visual):
        raise ValueError('Frozen v2.2 stage incomplete or output changed')
    data=json.loads(visual.read_text());battle.check_identity(data['battle_id'])
    parent=Path(data['input_identity']['input'])
    if file_hash(parent)!=data['input_identity']['input_sha256']: raise ValueError('Frozen visual input changed')
    original=json.loads(parent.read_text());dependencies=original['input_identity']['inputs']
    candidates=[Path(p) for p in dependencies if p.endswith('/reconstruction.json')]
    if len(candidates)!=1:raise ValueError('Unique original snapshot evidence required')
    state_path=candidates[0]
    if file_hash(state_path)!=dependencies[str(state_path)]:raise ValueError('Snapshot source changed')
    states=json.loads(state_path.read_text());battle.check_identity(states['battle_id'])
    paths=[visual,visual_manifest,parent,state_path]
    event_paths=[Path(p) for p in states['input_hashes'] if p.endswith(('/events.json','/video-only.json'))]
    if len(event_paths)!=1:raise ValueError('Unique source event collection required')
    raw_path=event_paths[0]
    if file_hash(raw_path)!=states['input_hashes'][str(raw_path)]:raise ValueError('Original recognition events changed')
    paths.append(raw_path);raw=json.loads(raw_path.read_text());battle.check_identity(raw['battle_id'])
    return data,states,{e['event_id']:e for e in raw['events']},paths


def bind_team(result, team, roster_reviews, *, root=ROOT):
    """User-confirmed exact six-member match plus unique species-to-build mapping.

    Preserve every source instance ID, including unresolved duplicate identities;
    this attaches configured builds, and does not merge source individuals or
    overwrite their current battle form/ability/item.
    """
    builds=KnownBuilds();bid=result['battle_id']
    review=next((r for r in roster_reviews if r['battle_id']==bid),None)
    expected=[m['species_id'] for m in team.data['members']]
    if not review or review.get('matches_team7') is not True:
        return builds,dict(status='unbound',reason='complete_matching_roster_not_verified')
    if not review.get('reviewer') or sorted(review['species_ids'])!=sorted(expected) or len(set(expected))!=6:
        raise ValueError('Exact reviewed unique six-species roster required')
    image=Path(root)/review['image']
    if not image.is_file() or file_hash(image)!=review['sha256']:raise ValueError('Roster review source missing or changed')
    assertion=team.data.get('binding_policy',{})
    if assertion.get('asserted_by')!='user' or not assertion.get('statement'):raise ValueError('User same-build confirmation required')
    members={m['species_id']:m for m in team.data['members']};bindings={};unresolved=[]
    for a in result['actions']:
        if a['side']!='self' or not a['actor_identity_reliable']:continue
        species=a.get('observed_species')
        entity=team.knowledge.entities.get(species)
        if entity is None or entity.kind!='species':
            unresolved.append(a['id']);continue
        sid=entity.species_id;member=members.get(sid)
        if not member:unresolved.append(a['id']);continue
        pid=a['instance_id'];fields=member['fields']
        if (bid,pid) in builds.records:continue
        builds.register(battle_id=bid,instance_id=pid,record=dict(
            identity=fields['identity']['canonical_id'],form='as_named',verified=True,
            observed_stats={s:fields[s]['value'] for s in ('hp','attack','defense','special_attack','special_defense','speed')},
            ability=fields['ability']['canonical_id'],item=fields['held_item']['canonical_id'],
            evidence=[dict(team_id=team.data['team_id'],member_id=member['instance_id'],user_assertion=assertion,
                           roster_review=review,identity_basis='unique species in confirmed six-member team; source instance continuity not merged')]))
        bindings[pid]=member['instance_id']
    return builds,dict(status='user_confirmed_roster_bound',bindings=bindings,unresolved_actions=unresolved,
        source_instance_continuity='Unchanged; multiple source IDs are not automatically the same battle individual')


def report(result):
    c=result['counts'];speed=result['speed'];lines=[f"# {result['battle_id']} — M3.4.1 action-order audit",'',
        'Frozen v2.2 local membership; recognized announcements are separate from numeric evidence.', '',
        '| Metric | Count |','| --- | ---: |']
    for k,v in c.items():
        if isinstance(v,int):lines.append(f'| {k} | {v} |')
    lines += [f"| eligible posterior updates | {speed['eligible_updates']} |",f"| actual information gain (nats) | {speed['information_gain_nats']} |",'',
        'Build binding: '+result['build_binding']['status']+'. Configured Speed does not establish current battle form or effective Speed.','',
        'Numeric blockers: `'+json.dumps(c['numeric_blockers'],ensure_ascii=False,sort_keys=True)+'`.','',
        'Non-action message classes: `'+json.dumps(c['categories'],ensure_ascii=False,sort_keys=True)+'`.','',
        'Chronological traces (source recognition, not curated complete turn ground truth):','']
    byid={a['id']:a for a in result['actions']}
    for group in result['groups'][:3]:
        lines += [f"Local segment {group['local_index']} (`{group['turn_id']}`), {group['membership_status']}; partial:",'',
            '| Time (s) | Actor / source instance | Move | Effective priority support | Source event |', '| ---: | --- | --- | --- | --- |']
        for aid in group['action_ids']:
            a=byid[aid];p=a['priority'];label=(a['text'] or '').replace('\n',' ').replace('|',' ')
            lines.append(f"| {a['timestamp']:.3f} | {a['side']} `{a['instance_id']}` | {label} (`{a['move']}`) | {p['effective_priorities']} / {p['status']} | `{a['event_id']}` |")
        lines += ['','All source images, immutable IDs, snapshots, modifier uncertainty and omitted relations are preserved in the fingerprinted action JSON.','']
    return '\n'.join(lines)+'\n'


def run(n, *, root=ROOT, reviews=None, profile='champions-evidence-only-v1'):
    battle=BattleArtifacts(f'sample_battle_{n}',root).prepare();data,states,raw,paths=inputs_for(battle)
    team_path=Path(root)/'tests/fixtures/battle_evidence/sample-team7-reviewed.json'
    rosters_path=Path(root)/'tests/fixtures/battle_evidence/team7-roster-bindings.json'
    paths += [team_path,rosters_path];team=TeamConfiguration.load(team_path)
    roster_reviews=json.loads(rosters_path.read_text())['roster_reviews']
    roster=next((r for r in roster_reviews if r['battle_id']==battle.battle_id),None)
    if roster:paths.append(Path(root)/roster['image'])
    deps=[Path(__file__),Path(__file__).with_name('actions.py'),Path(__file__).with_name('action_inference.py'),
          Path(__file__).with_name('order_mechanics.py'),Path(__file__).with_name('order-mechanics-v1.json'),
          Path(__file__).with_name('builds.py'),ROOT/'speed_order/execution.py',ROOT/'speed_order/core.py',
          ROOT/'speed_inference/likelihood.py',ROOT/'speed_inference/posterior.py',ROOT/'speed_inference/domains.py',
          ROOT/'battle_artifacts.py',ROOT/'team_configuration/__init__.py',ROOT/'knowledge/__init__.py',
          ROOT/'knowledge/champions_stats.py',ROOT/'knowledge/identity.py',ROOT/'damage/core.py',
          ROOT/'knowledge/data/champions_stat_rules.json',ROOT/'speed_order/data/sources-v1.json',
          ROOT/'knowledge/data/manifest.json']
    identity=dict(version=VERSION,inputs={str(p):file_hash(p) for p in paths},
        dependencies={str(p):file_hash(p) for p in deps},reviews=reviews,profile=profile,
        knowledge_snapshot=team.knowledge.snapshot_id)
    dest=battle.cache('m341-actions/'+digest(identity)[:16]);dest.mkdir(parents=True,exist_ok=True)
    manifest=dest/'manifest.json';output=dest/'actions.json';summary=dest/'summary.md'
    if manifest.exists():
        m=json.loads(manifest.read_text())
        if m.get('status')=='complete' and all((dest/k).exists() and file_hash(dest/k)==v for k,v in m['outputs'].items()):
            return dict(battle_id=battle.battle_id,result=str(output),reused=True)
    started=time.perf_counter();m=dict(status='running',identity=identity,stage='actions');atomic_json(manifest,m)
    try:
        result=reconstruct(data,states['snapshots'],source_events=raw,reviews=(reviews or {}).get('actions'))
        # Include contemporaneous UI observations as uncertain evidence, never as
        # certified Tailwind side or hidden-extension duration.
        result['counter_observations']=data['counter_observations']
        result['counter_constraints']=data['counter_constraints']
        builds,binding=bind_team(result,team,roster_reviews,root=root);result['build_binding']=binding
        result=analyse(result,builds,profile=profile,comparisons=(reviews or {}).get('comparisons'))
        result['input_identity']=identity;atomic_json(output,result);summary.write_text(report(result))
        m.update(status='complete',stage='complete',outputs={'actions.json':file_hash(output),'summary.md':file_hash(summary)},
                 metrics=dict(seconds=time.perf_counter()-started,video_decodes=0,ocr_calls=0,state_engine_replays=0))
        atomic_json(manifest,m)
        concise=battle.report('M3.4.1-action-order-validation.md');concise.write_text(report(result))
        return dict(battle_id=battle.battle_id,result=str(output),reused=False,counts=result['counts'],speed=result['speed']['eligible_updates'])
    except Exception as exc:
        m.update(status='failed',error=repr(exc));atomic_json(manifest,m);raise
