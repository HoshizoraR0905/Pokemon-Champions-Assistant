"""Exact bounded Speed inference and read-only decision comparisons."""
from copy import deepcopy
from itertools import islice
import json
from knowledge.stat_feasibility import champions_attainable_stats, summary
from .core import evaluate_order, provenance, need, integer, shape, text, Issue, REFERENCE, PROFILES
from .scenarios import assignments


def domain(values,limit=4096):
    try:values=list(islice(iter(values),limit+1))
    except TypeError:raise Issue('insufficient_information','Explicit finite Speed candidates required')
    need(0<len(values)<=limit,'Empty/over-limit candidate domain')
    for v in values:integer(v,1,4095)
    return sorted(set(values))


def infer_speed(*,observations,candidate_speeds=None,profile='champions-evidence-only-v1',variables=None,
                champions=None,max_assignments=128,max_evaluations=100000):
    result=dict(schema_version=1,status='insufficient_information',feasible=None,numerical_feasible=None,
        candidate_domain=[],scenarios=[],per_observation=[],conflict=None,diagnostics=[],
        champions=None,compatible_training=None,provenance=provenance(),work={'evaluations':0,'memo_hits':0})
    try:
        json.dumps([observations,variables,champions],allow_nan=False)
        integer(max_assignments,1,1024);integer(max_evaluations,1,1000000)
        need(isinstance(profile,str) and profile in PROFILES,'Explicit supported rules profile required')
        legal=None
        if champions is not None:
            need(isinstance(champions,dict),'Champions identity/constraints required')
            legal=champions_attainable_stats(stat='speed',**champions);result['champions']=legal
            need(legal['joint_feasible'] is not None,'Unresolved Champions legal domain')
        values=domain(candidate_speeds) if candidate_speeds is not None else (legal['joint_feasible']['values'] if legal is not None else domain(None))
        result['candidate_domain']=values
        need(isinstance(observations,list) and observations,'One or more order observations required')
        contexts={};subjects=[];identities=set();orders={};noninformative={}
        from .core import identity_key
        for obs in observations:
            shape(obs,{'id','battle_id','stat_epoch','sequence','evidence_kind','context'})
            need(all(text(obs[k]) for k in ('id','battle_id','stat_epoch')),'Stable observation/battle/stat epoch required')
            need(obs['id'] not in contexts,'Duplicate observation ID')
            need(obs['sequence'] in (['own','opponent'],['opponent','own']),'Explicit two-action sequence required')
            participant=obs['context']['opponent']
            identities.add(identity_key(participant['identity'],participant['form']))
            need(text(participant['instance_id']),'Opponent instance identity required')
            subjects.append((obs['battle_id'],obs['context']['opponent']['instance_id'],obs['stat_epoch']))
            contexts[obs['id']]=obs['context'];orders[obs['id']]=obs['sequence'][0]
            if obs['evidence_kind']!='verified_action_order':noninformative[obs['id']]='Animation timestamps/uncertain extraction are not established action-order evidence.'
        need(len(set(subjects))==1 and len(identities)==1,'Do not combine different instances, forms, battles or stat epochs')
        if legal is not None:need(identities=={legal['identity']},'Legal domain species/form does not match the inferred instance')
        count,variants=assignments(contexts,variables or [],max_assignments)
        need(count*len(values)*len(observations)<=max_evaluations,'Speed evaluation limit exceeded')
        memo={};all_sets=[];individual={oid:set() for oid in contexts};informed={oid:False for oid in contexts}
        for index,(assignment,variant) in enumerate(variants):
            rows=[];sets=[]
            for oid,context in variant.items():
                compatible=set();details=[];reasons=set();informative=False
                for candidate in values:
                    if oid in noninformative:
                        outcome=dict(status='assessed',kind='non_informative',reason=noninformative[oid])
                    else:
                        key=json.dumps([context,candidate,profile],sort_keys=True,allow_nan=False)
                        if key in memo:outcome=memo[key];result['work']['memo_hits']+=1
                        else:
                            outcome=evaluate_order(context=context,opponent_speed=candidate,profile=profile)
                            memo[key]=outcome;result['work']['evaluations']+=1
                    if outcome['status']!='assessed':
                        result['status']=outcome['status'];result['diagnostics'].append(dict(observation_id=oid,assignment=assignment,reason=outcome['reason']));return result
                    if outcome['kind']=='speed':
                        informative=True
                        if orders[oid] in outcome['orders']:
                            compatible.add(candidate);details.append(dict(candidate=candidate,own_effective=outcome['own']['effective_speed'],opponent_effective=outcome['opponent']['effective_speed'],tie=outcome['tie']))
                    else:
                        compatible.add(candidate);reasons.add(outcome['reason'])
                        if outcome['kind']=='priority' and outcome['winner']!=orders[oid]:
                            reasons.add('Observed sequence conflicts with the audited priority winner; not used as a Speed constraint.')
                sets.append(compatible);individual[oid].update(compatible);informed[oid]|=informative
                rows.append(dict(id=oid,informative=informative,reasons=sorted(reasons),feasible=summary(compatible),compatibility=details))
            joint=set.intersection(*sets) if sets else set(values);all_sets.append(sets)
            result['scenarios'].append(dict(id=str(index),assignment=assignment,feasible=summary(joint),per_observation=rows))
        numerical=set().union(*(set(s['feasible']['values']) for s in result['scenarios']))
        final=numerical & set(legal['joint_feasible']['values']) if legal is not None else numerical
        result.update(status='empty' if not final else 'non_informative' if not any(informed.values()) else 'conditional' if variables else 'exact',
            feasible=summary(final),numerical_feasible=summary(numerical),
            per_observation=[dict(id=oid,feasible=summary(individual[oid]),informative=informed[oid]) for oid in contexts])
        if legal is not None:
            args=deepcopy(champions);constraints=deepcopy(args.get('stat_constraints') or {})
            constraints['speed']={'allowed_values':sorted(final)};args['stat_constraints']=constraints
            result['compatible_training']=champions_attainable_stats(stat='speed',**args)['configurations']
        if not numerical and not values:
            result['conflict']=dict(reason='The supplied Champions candidate domain is empty before order constraints; no observation conflict is asserted.')
        elif not numerical:
            ids=list(contexts);core=list(range(len(ids)))
            for i in list(core)[:128]:
                trial=[j for j in core if j!=i]
                if not any(set.intersection(*(s[j] for j in trial)) if trial else set(values) for s in all_sets):core=trial
            result['conflict']=dict(observation_ids=[ids[i] for i in core],minimal_by_deletion=len(ids)<=128,
                review='Check stat epoch, identity, missing priority/order modifiers and order-decision timing; no constraints widened.')
        elif not final:result['conflict']=dict(reason='Numerical order constraints have no joint Champions training configuration.')
        result['provenance']=dict(sources=provenance(),observations=deepcopy(observations),variables=deepcopy(variables or []),profile=profile,
            assumption='One unchanged underlying actual Speed across observations; input states apply at each explicitly evidenced order decision.')
    except (Issue,ValueError,TypeError,KeyError,NotImplementedError) as exc:result['diagnostics'].append(dict(reason=str(exc)))
    return result


def compare_speed(*,context,opponent_speeds,profile='champions-evidence-only-v1',variables=None,max_assignments=128,max_evaluations=100000):
    result=dict(schema_version=1,status='insufficient_information',explanation='',own_guaranteed_first=False,
        opponent_guaranteed_first=False,speed_tie_possible=False,possible_first=[],scenarios=[],diagnostics=[],provenance=provenance())
    try:
        values=domain(opponent_speeds);integer(max_assignments,1,1024);integer(max_evaluations,1,1000000)
        json.dumps([context,variables],allow_nan=False)
        count,variants=assignments({'query':context},variables or [],max_assignments)
        need(count*len(values)<=max_evaluations,'Comparison evaluation limit exceeded')
        possible=set();non_tie=set();tie=False;speed_seen=False;priority_seen=False
        for assignment,variant in variants:
            rows=[]
            for candidate in values:
                outcome=evaluate_order(context=variant['query'],opponent_speed=candidate,profile=profile)
                if outcome['status']!='assessed':
                    result['status']=outcome['status'];result['explanation']=outcome['reason'];return result
                if outcome['kind']=='speed':
                    possible.update(outcome['orders']);tie|=outcome['tie'];speed_seen=True
                    if not outcome['tie']:non_tie.update(outcome['orders'])
                elif outcome['kind']=='priority':possible.add(outcome['winner']);priority_seen=True
                elif outcome['kind']=='non_speed_ordering':
                    result.update(status='non_speed_ordering',explanation=outcome['reason']);return result
                else:result['explanation']=outcome['reason'];return result
                rows.append(dict(candidate=candidate,result=outcome))
            result['scenarios'].append(dict(assignment=assignment,comparisons=rows))
        own=possible=={'own'};opponent=possible=={'opponent'}
        status='non_speed_ordering' if priority_seen and not speed_seen else 'speed_tie_possible' if tie else 'own_guaranteed_first' if own else 'opponent_guaranteed_first' if opponent else 'mixed_order_possible'
        result.update(status=status,own_guaranteed_first=own,opponent_guaranteed_first=opponent,
            speed_tie_possible=tie,possible_first=sorted(possible),
            non_tie_possible_first=sorted(non_tie),tie_only_uncertainty=tie and len(non_tie)<=1,
            non_tie_order_varies=len(non_tie)>1,
            explanation='Priority determines order across all supplied candidates/scenarios.' if priority_seen and not speed_seen else
              'Equal effective Speed is possible; tie resolution permits either order. See scenario rows for other possible outcomes.' if tie else
              'Your Pokémon acts first in every supplied candidate/scenario.' if own else
              'The opponent acts first in every supplied candidate/scenario.' if opponent else
              'Different feasible Speeds or scenarios permit different action orders.')
    except (Issue,ValueError,TypeError,KeyError) as exc:result['explanation']=str(exc);result['diagnostics'].append(str(exc))
    return result
