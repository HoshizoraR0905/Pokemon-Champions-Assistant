"""Source-reviewed additions to sealed replay; no OCR or battle-specific answers.

Every calculation is conditional on the review's explicit state. Native-domain
projections use existing construction, item classes and v2 ordering arithmetic.
"""
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from speed_order import configuration_domain, infer_speed
from speed_order.core import identity_key, knowledge, name
from speed_order.forms import mega_base_form, published_ability, training_stats
from speed_order.dynamic import prepare_state
from speed_order.mechanics import action_metrics
from knowledge.stat_feasibility import summary
from .speed_adapter import own_form_speed
from .speed_items import item_classes
from .speed_replay import universe
from .speed_replay_offline import file_hash

PROFILE = 'showdown-champions-reference-v1'


def evidence(events, basis='direct'):
    return dict(sources=[s['source_id'] for e in events for s in e['sources']],
                basis=basis, confidence='agent reviewed original frames; conditions separately stated')


def reviewed_action(event, selection=None):
    kind = {'executed_move':'move','prevented_action':'move','voluntary_switch':'voluntary_switch',
            'mega_evolution':'mega_evolution'}[event['kind']]
    a = dict(id=event['id'], individual=event['individual'], kind=kind, move=event['move'],
             outcome=event['outcome'], changes=[], evidence=evidence([event]),
             activation=dict(state='unknown', coverage_complete=False,evidence=evidence([event])))
    if a['outcome'] == 'flinched':
        if selection is None or selection['move'] != event['move'] or selection['timestamp'] > event['timestamp']:
            raise ValueError('Prevented action requires earlier independent selected-move evidence')
        a['selection_evidence'] = evidence([selection])
        a['timing_evidence'] = evidence([event], 'user_requirement')
    return a


def projection(configs, classes):
    branches = defaultdict(list)
    for c in configs:
        branches[(c['item'], c['ability'], c['form'])].append(c['speed'])
    class_items = {x['representative']:x['members'] for x in classes}
    return dict(speed=summary(c['speed'] for c in configs), configuration_count=len(configs),
        items=sorted({item for c in configs for item in class_items.get(c['item'], [c['item']])}),
        abilities=sorted({c['ability'] for c in configs}),
        branches=[dict(item=item, concrete_items=class_items.get(item,[item]),ability=ability,form=form,
                       speed=summary(values)) for (item,ability,form), values in sorted(branches.items())])


def compressed(configs):
    """Exact ordering equivalence only while no training/form changes are supplied."""
    groups = defaultdict(list)
    for c in configs:
        groups[(c['speed'],c['ability'],c['item'],c['form'])].append(c)
    representatives = []
    mapping = {}
    for i, group in enumerate(groups.values()):
        c = dict(deepcopy(group[0]),id=str(i),training=None)
        representatives.append(c); mapping[c['id']]=group
    return representatives, mapping


def infer_pair(configs, observation):
    if not configs:
        return [], dict(status='empty', feasible=summary([]),tie_compatible=[],excluded_configurations=[])
    if any(a['changes'] for a in observation['actions']) or observation['initial_changes'] or observation['alternatives']:
        raise ValueError('Training equivalence requires fixed forms and explicit fixed action states')
    compact, mapping = compressed(configs)
    result = infer_speed(schema_version=2,observations=[observation],configurations=compact,profile=PROFILE,
                         max_evaluations=1000000)
    if result['status'] not in {'exact','empty'}:
        return None, result
    ids = {r['configuration']['id'] for r in result['compatible_configurations']}
    survivors = [c for i in ids for c in mapping[i]]
    # Compact audit retains complete exclusion groups, no enormous duplicate traces.
    receipt = dict(status=result['status'], feasible=result['feasible'], work=result['work'],
        tie_compatible=[c['id'] for i in result['tie_compatible'] for c in mapping[i]],
        excluded_configurations=[c['id'] for i in mapping if i not in ids for c in mapping[i]],
        representative_count=len(compact),configuration_count=len(configs),
        remaining_items=result['remaining_items'],remaining_abilities=result['remaining_abilities'],
        diagnostics=result['diagnostics'])
    return survivors, receipt


def joint_phase_support(left, right, state, actions):
    """Exact binary relation, retaining key witnesses rather than cartesian builds.

    No cycles or independent marginal substitutions: this handles one binary
    same-phase decision, retaining persistent complete configuration identities.
    """
    if len(actions)!=2 or actions[0]['kind']!=actions[1]['kind'] or actions[0]['kind'] not in {'voluntary_switch','mega_evolution'}:
        raise ValueError('Joint relation requires one supported comparable phase')
    keys = []
    for configs, action in zip([left,right],actions):
        metrics = {}
        for c in configs:
            p=deepcopy(state['participants'][action['individual']])
            p.update(actual_speed=c['speed'],ability=c['ability'],item=c['item'])
            prepared=prepare_state(dict(participants={p['instance_id']:p},field=state['field']))
            metrics[c['id']]=action_metrics(action,prepared['participants'][p['instance_id']],state['field'],0,PROFILE)['key']
        keys.append(metrics)
    if not left or not right:
        return [],[],dict(status='empty',relation=None)
    left_keys=set(keys[0].values());right_keys=set(keys[1].values())
    allowed={a:{b for b in right_keys if a>=b} for a in left_keys}
    kept_left=[c for c in left if allowed[keys[0][c['id']]]]
    kept_right=[c for c in right if any(keys[1][c['id']] in bs for bs in allowed.values())]
    branch_pairs=[]
    for li in sorted({c['item'] for c in left}):
        ls=[c for c in left if c['item']==li]
        for ri in sorted({c['item'] for c in right}):
            rs=[c for c in right if c['item']==ri]
            slowest_right=min(keys[1][r['id']] for r in rs)
            fastest_left=max(keys[0][l['id']] for l in ls)
            lvalues=[c['speed'] for c in ls if keys[0][c['id']]>=slowest_right]
            rvalues=[c['speed'] for c in rs if keys[1][c['id']]<=fastest_left]
            branch_pairs.append(dict(first_item_class=li,second_item_class=ri,
                                     first_speed=summary(lvalues),second_speed=summary(rvalues)))
    return kept_left,kept_right,dict(status='exact' if kept_left else 'empty',
        relation='first key >= second key, ties allowed; evaluated at one shared decision',
        key_by_configuration=[{i:list(k) for i,k in mapping.items()} for mapping in keys],
        compatible_key_pairs=[[list(a),list(b)] for a,bs in allowed.items() for b in bs],item_branch_pairs=branch_pairs)


def empirical_configs(index, identity, classes):
    mapping={name(item,'item'):c['representative'] for c in classes for item in c['members']}
    configs=[]; unresolved=[]
    source_forms=[identity]
    # A published Mega identity denotes an eventual form, not an already active
    # transformation. Its original joint build can support a pre-Mega snapshot.
    if mega_base_form(identity) is None:
        source_forms += [key for key in index.by_species if key != identity and mega_base_form(key) == identity]
    for row in (r for key in source_forms for r in index.by_species.get(key, [])):
        if not row['complete']:
            continue
        try:
            ability_state=published_ability(row['species'],row['ability'],identity)
            item=name(row['item'],'item')
            required=knowledge().facts['pokemon'][row['species']].get('required_item')
            if required and item != required:
                raise ValueError('Published Mega configuration lacks its required stone')
            if item not in mapping:
                raise ValueError('Published item outside supported item domain')
            training=dict(alignment=deepcopy(row['alignment']),
                          point_domains={s:[v] for s,v in row['training_points'].items()})
            speed=training_stats(identity,training)['speed'][0]
        except ValueError as exc:
            unresolved.append(dict(build_id=row['build_id'],observed_team_signature=row['observed_team_signature'],reason=str(exc)))
            continue
        configs.append(dict(id=row['observed_team_signature']+':'+str(row['build_id']),speed=speed,
            ability=ability_state['active_ability'],ability_state=ability_state,
            item=mapping[item],form=identity,training=training,observed_build=deepcopy(row)))
    return configs,unresolved


def apply_review(replay, review, builds, index, *, root, empirical_mode='expand_on_contradiction', expand=False):
    if empirical_mode not in {'empirical_only','expand_on_contradiction','full_legal'}:
        raise ValueError('Unknown empirical search mode')
    if replay['battle_id']!=review['battle_id'] or review['origin']!='recorded':
        raise ValueError('Cross-battle or synthetic attachment rejected')
    events={e['id'].rsplit(':',1)[-1]:e for e in review['events']}
    frame_sources={f['source_id']:f for f in replay['frames']}
    for e in events.values():
        if not e['sources'] or not e.get('reviewer'):
            raise ValueError('Source reviewer required')
        for s in e['sources']:
            frame=frame_sources.get(s['source_id'])
            if not frame or frame['timestamp']>e['timestamp'] or frame['image']!=s['image'] or file_hash(Path(root)/s['image'])!=s['sha256']:
                raise ValueError('Review source is missing, altered, mismatched or in the future')
    own_states=[]
    for e in sorted(events.values(),key=lambda e:e['timestamp']):
        if not e.get('current_form'):
            continue
        matches=[builds[i] for i in review['identity_links'][e['individual']] if i in builds]
        if not matches:
            raise ValueError('Reviewed form stat transition requires own verified build')
        key=identity_key(e['current_form'],'as_named' if e['current_form'].startswith('Mega ') else 'base')
        speed,reason=own_form_speed(matches[0],key,timestamp=e['timestamp'])
        if reason: raise ValueError(reason)
        own_states.append(dict(timestamp=e['timestamp'],individual=e['individual'],current_form=key,
            unmodified_speed=speed,event_id=e['id'],sources=e['sources'],
            stat_basis='Verified TeamConfiguration training/alignment and canonical current-form stats; in-battle modifiers separate'))
    domains={}; empirical={}; classes={}; updates=[]; empirical_issues={}; inherited_conditions={}
    for comparison in review['comparisons']:
        start=perf_counter()
        pair=[events[comparison[k]] for k in ['before','after']]
        if pair[0]['timestamp']>=pair[1]['timestamp']:
            raise ValueError('Reviewed action chronology conflict')
        state=dict(participants={},field=deepcopy(comparison['field']))
        identities={}
        for actor,template in comparison['actors'].items():
            p=deepcopy(template);p['instance_id']=actor
            identity=identity_key(p['identity'],p['form']);identities[actor]=identity
            if actor not in review['identity_links']:
                raise ValueError('Stable individual binding required')
            own=[builds[i] for i in review['identity_links'][actor] if i in builds]
            if own:
                speed,reason=own_form_speed(own[0],identity,timestamp=pair[-1]['timestamp'])
                if reason: raise ValueError(reason)
                ability = (own[0]['ability'] if identity==own[0]['canonical_identity'] else
                           knowledge().facts['pokemon'][identity]['ability_names'][0])
                p.update(actual_speed=speed,ability=ability,item=own[0]['item'])
            else:
                p.update(actual_speed=None,ability=p.get('ability'),item=p.get('item'))
                if actor not in domains:
                    u=universe(identity);classes[actor]=u['item_equivalence_classes']
                    domains[actor]=configuration_domain(identity=identity,form='as_named' if knowledge().entities[identity].form_id else 'base',
                        abilities=u['abilities'],items=u['item_representatives'],max_configurations=100000)['configurations']
                    empirical[actor],empirical_issues[actor]=empirical_configs(index,identity,classes[actor])
            state['participants'][actor]=p
        actions=[reviewed_action(e,events.get('selection')) for e in pair]
        subject=comparison['subject']
        before={a:projection(domains[a],classes[a]) for a in comparison['actors'] if a in domains}
        empirical_before={a:projection(empirical[a],classes[a]) for a in before}
        if comparison['kind']=='known_own_vs_hidden':
            observation=dict(id=comparison['id'],battle_id=replay['battle_id'],decision_id=comparison['id'],subject=subject,
                state=state,actions=actions,sequence=[e['id'] for e in pair],initial_changes=[],alternatives=[],strict_speed=[],evidence=evidence(pair))
            observed_survivors,observed_receipt=infer_pair(empirical[subject],observation) if empirical[subject] else ([],dict(status='empty'))
            survivors,receipt=infer_pair(domains[subject],observation)
            if survivors is not None: domains[subject]=survivors
            if observed_survivors is not None: empirical[subject]=observed_survivors
        else:
            l,r=[a['individual'] for a in actions]
            domains[l],domains[r],receipt=joint_phase_support(domains[l],domains[r],state,actions)
            empirical[l],empirical[r],observed_receipt=joint_phase_support(empirical[l],empirical[r],state,actions)
        conditions=set(comparison['assumptions'])
        for a in before: conditions.update(inherited_conditions.get(a,[]))
        for a in before: inherited_conditions[a]=sorted(conditions)
        expanded = expand or empirical_mode=='full_legal' or (empirical_mode=='expand_on_contradiction' and observed_receipt['status']=='empty')
        updates.append(dict(id=comparison['id'],timestamp=pair[-1]['timestamp'],status=receipt['status'],
            inherited_conditions=sorted(conditions),empirical_issues=deepcopy(empirical_issues),
            search=dict(mode=empirical_mode,expanded=expanded,manual_expansion=expand,
                empirical_status=observed_receipt['status'],
                search_result_layer='full_legal' if expanded else 'observed_complete_builds',
                note='Full model evaluated independently for authoritative display; observed support is never relabeled legal'),
            scope=comparison['scope'],assumptions=deepcopy(comparison['assumptions']),state=state,actions=actions,
            before=before,empirical_before=empirical_before,
            after={a:projection(domains[a],classes[a]) for a in before},
            empirical_after={a:projection(empirical[a],classes[a]) for a in before},
            empirical_survivor_ids={a:[c['id'] for c in empirical[a]] for a in before},
            model_survivor_ids={a:[c['id'] for c in domains[a]] for a in before},
            solver=receipt, empirical_solver=observed_receipt, seconds=perf_counter()-start,
            evidence=deepcopy(pair + ([events['selection']] if any(a['outcome']=='flinched' for a in actions) else [])),
            own_speed={a:p['actual_speed'] for a,p in state['participants'].items() if p['actual_speed'] is not None},
            empirical_interpretation='Observed joint builds; never the complete legal domain; legal support always computed separately'))
    return dict(review=review,updates=updates,own_states=own_states,solver_seconds=sum(u['seconds'] for u in updates),
                scope='Full native/catalog/SP support under explicit reviewed state and pinned mechanics; conditional continuity is labeled')
